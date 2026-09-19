from __future__ import annotations

import uuid
from typing import Any

from endstone import Player

from .auto_bind import VoiceCraftEndstone as VoiceCraftEndstone022


class VoiceCraftEndstone(VoiceCraftEndstone022):
    """Endstone 0.2.6: automatic rebind plus safe manual disconnect."""

    version = "0.2.6"
    _RECONNECT_FORM_DELAY_TICKS = 100  # 5 seconds at 20 TPS
    _UNBIND_TIMEOUT_TICKS = 400  # 20 seconds at 20 TPS
    _MAX_EXPIRED_UNBINDS = 128

    def __init__(self) -> None:
        super().__init__()
        self._rebind_waiting: set[str] = set()
        self._bound_entity_by_player: dict[str, int] = {}
        self._pending_unbind_requests: dict[str, str] = {}
        self._pending_unbind_entities: dict[str, int] = {}
        # A timed-out destructive request is not assumed to have failed. Keep a
        # bounded tombstone so a late success can still reconcile local state.
        self._expired_unbind_requests: dict[str, tuple[str, int]] = {}
        self._manual_unbound_entities: set[int] = set()

    def on_disable(self) -> None:
        self._rebind_waiting.clear()
        self._bound_entity_by_player.clear()
        self._pending_unbind_requests.clear()
        self._pending_unbind_entities.clear()
        self._expired_unbind_requests.clear()
        self._manual_unbound_entities.clear()
        super().on_disable()

    def handle_player_quit(self, player: Player) -> None:
        player_key = self._player_key(player)
        self._rebind_waiting.discard(player_key)
        self._bound_entity_by_player.pop(player_key, None)
        self._pending_unbind_requests.pop(player_key, None)
        self._pending_unbind_entities.pop(player_key, None)
        for request_id, (expired_player_key, _) in list(self._expired_unbind_requests.items()):
            if expired_player_key == player_key:
                self._expired_unbind_requests.pop(request_id, None)
        super().handle_player_quit(player)

    def _handle_bind_result(self, message: dict[str, Any]) -> None:
        player_key = self._resolve_bind_player_key(message)
        success = bool(message.get("success", False))
        super()._handle_bind_result(message)

        if not success or not player_key:
            return

        self._rebind_waiting.discard(player_key)
        self._pending_unbind_requests.pop(player_key, None)
        self._pending_unbind_entities.pop(player_key, None)
        try:
            entity_id = int(message.get("entityId"))
        except (TypeError, ValueError):
            entity_id = None
        if entity_id is not None:
            self._bound_entity_by_player[player_key] = entity_id

    def _request_manual_unbind(self, player: Player) -> bool:
        player_key = self._player_key(player)
        if player_key not in self._bound_players:
            player.send_message("VoiceCraft is not currently bound.")
            return False
        if player_key in self._pending_unbind_requests:
            player.send_message("VoiceCraft disconnect is already in progress.")
            return False

        entity_id = self._bound_entity_by_player.get(player_key)
        if entity_id is None:
            player.send_error_message("VoiceCraft bound entity is unavailable. Open /vc Status and try again.")
            return False
        if self._bridge is None or not self._bridge.connected or not self._bridge.android_connected:
            player.send_error_message(
                "VoiceCraft mobile server is not reachable right now. Disconnect was not queued; try again after the bridge reconnects."
            )
            return False

        request_id = uuid.uuid4().hex
        queued = self._bridge_send(
            {
                "type": "unbind",
                "requestId": request_id,
                "name": str(player.name),
                "xuid": str(player.xuid or ""),
                "uuid": str(player.unique_id),
                "entityId": entity_id,
            }
        )
        if not queued:
            player.send_error_message("VoiceCraft bridge queue is unavailable; disconnect was not sent.")
            return False

        self._pending_unbind_requests[player_key] = request_id
        self._pending_unbind_entities[player_key] = entity_id
        self._rebind_waiting.discard(player_key)
        self._schedule_unbind_timeout(player_key, request_id, entity_id)
        player.send_message("VoiceCraft: disconnect request sent to the mobile server.")
        self.logger.info(
            f"UNBIND requested player={player.name} xuid={player.xuid} entity={entity_id} request={request_id[:8]}"
        )
        return True

    def _remember_expired_unbind(self, request_id: str, player_key: str, entity_id: int) -> None:
        self._expired_unbind_requests[request_id] = (player_key, entity_id)
        while len(self._expired_unbind_requests) > self._MAX_EXPIRED_UNBINDS:
            oldest = next(iter(self._expired_unbind_requests), None)
            if oldest is None:
                break
            self._expired_unbind_requests.pop(oldest, None)

    def _schedule_unbind_timeout(self, player_key: str, request_id: str, entity_id: int) -> None:
        def callback() -> None:
            if self._pending_unbind_requests.get(player_key) != request_id:
                return
            if self._pending_unbind_entities.get(player_key) != entity_id:
                return

            self._pending_unbind_requests.pop(player_key, None)
            self._pending_unbind_entities.pop(player_key, None)
            self._remember_expired_unbind(request_id, player_key, entity_id)

            player = self._find_online_player(player_key)
            if player is not None:
                player.send_error_message(
                    "VoiceCraft disconnect confirmation timed out. The result is unknown; if your voice client is still connected, retry from /vc after the bridge is healthy."
                )
            self.logger.warning(
                f"UNBIND timeout player_key={player_key[:12]} entity={entity_id} request={request_id[:8]}; late result will still be reconciled"
            )

        try:
            self.server.scheduler.run_task(
                self,
                callback,
                delay=self._UNBIND_TIMEOUT_TICKS,
            )
        except Exception as exc:
            # Keep the request pending if the timeout task cannot be scheduled;
            # silently dropping confirmation tracking would be less safe.
            self.logger.warning(
                f"UNBIND timeout schedule failed player_key={player_key[:12]} request={request_id[:8]}: {type(exc).__name__}: {exc}"
            )

    def _drain_bridge_messages(self) -> None:
        if self._bridge is None:
            return
        for message in self._bridge.drain_incoming():
            kind = str(message.get("type", ""))
            if kind == "request_snapshot":
                self._send_full_snapshot()
            elif kind == "bind_result":
                self._handle_bind_result(message)
            elif kind == "unbind_result":
                self._handle_unbind_result(message)
            elif kind == "voice_client_disconnected":
                self._handle_voice_client_disconnected(message)

    def _handle_unbind_result(self, message: dict[str, Any]) -> None:
        player_key = str(message.get("xuid", "") or message.get("uuid", ""))
        request_id = str(message.get("requestId", ""))
        if not player_key or not request_id:
            return

        late_result = False
        if self._pending_unbind_requests.get(player_key) == request_id:
            entity_id = self._pending_unbind_entities.pop(player_key, None)
            self._pending_unbind_requests.pop(player_key, None)
        else:
            expired = self._expired_unbind_requests.pop(request_id, None)
            if expired is None or expired[0] != player_key:
                self.logger.info(
                    f"UNBIND stale result ignored player_key={player_key[:12] or '?'} request={request_id[:8] or '?'}"
                )
                return
            entity_id = expired[1]
            late_result = True

        success = bool(message.get("success", False))
        reason = str(message.get("reason", ""))[:160]
        player = self._find_online_player(player_key)

        if not success:
            if player is not None and not late_result:
                player.send_error_message(f"VoiceCraft disconnect failed: {reason or 'mobile server rejected the request'}")
            self.logger.warning(
                f"UNBIND {'late ' if late_result else ''}failure player_key={player_key[:12]} entity={entity_id} request={request_id[:8]} reason={reason or '-'}"
            )
            return

        current_entity = self._bound_entity_by_player.get(player_key)
        if entity_id is not None and current_entity is not None and current_entity != entity_id:
            # A late success for an old entity must never clear a newer binding.
            self.logger.info(
                f"UNBIND late success ignored for replaced entity player_key={player_key[:12]} entity={entity_id} current_entity={current_entity} request={request_id[:8]}"
            )
            return

        # If the player retried the same entity after a timeout, a late success
        # from the first request already achieved the desired disconnect. Clear
        # the newer local pending request too; its later result will be stale.
        if entity_id is not None and self._pending_unbind_entities.get(player_key) == entity_id:
            self._pending_unbind_entities.pop(player_key, None)
            self._pending_unbind_requests.pop(player_key, None)

        if entity_id is not None:
            self._manual_unbound_entities.add(entity_id)
            if len(self._manual_unbound_entities) > 256:
                self._manual_unbound_entities.pop()
        self._bound_entity_by_player.pop(player_key, None)
        self._bound_players.discard(player_key)
        self._pending_bind_keys.pop(player_key, None)
        self._pending_bind_requests.pop(player_key, None)
        self._rebind_waiting.discard(player_key)
        self._auto_bind_scheduled.discard(player_key)
        # Manual unbind means stay unbound until the player intentionally opens
        # /vc and binds again. This suppresses the automatic join/rebind form.
        self._auto_bind_shown.add(player_key)

        if player is not None:
            if late_result:
                player.send_message("VoiceCraft: disconnect completed after the timeout. Use /vc when you want to bind again.")
            else:
                player.send_message("VoiceCraft: disconnected successfully. Use /vc when you want to bind again.")
        self.logger.info(
            f"UNBIND {'late ' if late_result else ''}success player_key={player_key[:12]} entity={entity_id} request={request_id[:8]}; auto-rebind suppressed"
        )

    def _handle_voice_client_disconnected(self, message: dict[str, Any]) -> None:
        player_key = str(message.get("xuid", "") or message.get("uuid", ""))
        if not player_key or player_key in self._rebind_waiting:
            return

        try:
            disconnected_entity = int(message.get("entityId"))
        except (TypeError, ValueError):
            disconnected_entity = None

        pending_manual_entity = self._pending_unbind_entities.get(player_key)
        if disconnected_entity is not None and pending_manual_entity == disconnected_entity:
            self.logger.info(
                f"VOICE DISCONNECT manual-unbind race suppressed player_key={player_key[:12]} entity={disconnected_entity}"
            )
            return
        if disconnected_entity is not None and disconnected_entity in self._manual_unbound_entities:
            self._manual_unbound_entities.discard(disconnected_entity)
            self.logger.info(
                f"VOICE DISCONNECT post-unbind stale event suppressed player_key={player_key[:12]} entity={disconnected_entity}"
            )
            return

        expected_entity = self._bound_entity_by_player.get(player_key)
        if (
            expected_entity is not None
            and disconnected_entity is not None
            and disconnected_entity != expected_entity
        ):
            self.logger.info(
                f"VOICE DISCONNECT stale event ignored player_key={player_key[:12]} "
                f"entity={disconnected_entity} current_entity={expected_entity}"
            )
            return

        player = self._find_online_player(player_key)
        if player is None:
            return

        self._bound_entity_by_player.pop(player_key, None)
        self._bound_players.discard(player_key)
        self._pending_bind_keys.pop(player_key, None)
        self._pending_bind_requests.pop(player_key, None)
        self._auto_bind_shown.discard(player_key)
        self._rebind_waiting.add(player_key)

        player.send_error_message(
            "VoiceCraft หลุด! จะดำเนินการให้ใส่ Binding Key ใหม่อีกครั้งใน 5 วินาที..."
        )
        self.logger.info(
            f"VOICE DISCONNECT player={player.name} xuid={player.xuid}; rebind form scheduled in 5s"
        )

        def callback() -> None:
            self._rebind_waiting.discard(player_key)
            if player_key in self._bound_players or player_key in self._pending_bind_keys:
                return
            if self._find_online_player(player_key) is None:
                return
            self._auto_bind_shown.discard(player_key)
            self._show_auto_bind_form(player_key)

        try:
            self.server.scheduler.run_task(
                self,
                callback,
                delay=self._RECONNECT_FORM_DELAY_TICKS,
            )
        except Exception as exc:
            self._rebind_waiting.discard(player_key)
            self.logger.warning(
                f"REBIND FORM schedule failed player_key={player_key[:12]}: {type(exc).__name__}: {exc}"
            )
            self._schedule_auto_bind_form(player_key, self._RECONNECT_FORM_DELAY_TICKS)
