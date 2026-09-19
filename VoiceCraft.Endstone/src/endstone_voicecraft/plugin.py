from __future__ import annotations

import hashlib
import math
import time
import uuid
from typing import Any

from endstone import Player
from endstone.command import Command, CommandSender
from endstone.plugin import Plugin

from .bridge import EndstoneRelayClient
from .listener import VoiceCraftListener
from .model import PlayerState


class VoiceCraftEndstone(Plugin):
    prefix = "VoiceCraftEndstone"
    version = "0.2.0"
    api_version = "0.11"
    description = "VoiceCraft Endstone player-state and binding bridge"
    authors = ["SamSoSleepy"]

    commands = {
        "vcbind": {
            "description": "Bind this Minecraft player to a VoiceCraft client entity",
            "usages": ["/vcbind <key: str>"],
            "permissions": ["voicecraft.command.bind"],
        },
        "vcunbind": {
            "description": "Clear a pending VoiceCraft bind request",
            "usages": ["/vcunbind"],
            "permissions": ["voicecraft.command.bind"],
        },
        "vcstatus": {
            "description": "Show VoiceCraft Endstone bridge status",
            "usages": ["/vcstatus"],
            "permissions": ["voicecraft.command.status"],
        },
        "vcdump": {
            "description": "Dump tracked VoiceCraft player states",
            "usages": ["/vcdump"],
            "permissions": ["voicecraft.command.dump"],
        },
    }

    permissions = {
        "voicecraft.command.bind": {
            "description": "Allow a player to bind/unbind VoiceCraft.",
            "default": True,
        },
        "voicecraft.command.status": {
            "description": "Allow viewing VoiceCraft bridge status.",
            "default": True,
        },
        "voicecraft.command.dump": {
            "description": "Allow dumping all VoiceCraft player states.",
            "default": "op",
        },
    }

    def __init__(self) -> None:
        super().__init__()
        self._states: dict[str, PlayerState] = {}
        self._pending_bind_keys: dict[str, str] = {}
        self._pending_bind_requests: dict[str, str] = {}
        self._last_movement_log: dict[str, float] = {}
        self._interval_ticks = 2
        self._position_epsilon = 0.05
        self._rotation_epsilon = 1.0
        self._log_position_changes = False
        self._heartbeat_ticks = 600
        self._heartbeat_accumulator = 0
        self._bridge_enabled = False
        self._bridge: EndstoneRelayClient | None = None
        self._bridge_server_id = "mcsv-main"
        self._last_peer_state: tuple[bool, bool] | None = None

    def on_enable(self) -> None:
        self.save_default_config()
        self._load_settings()
        self.register_events(VoiceCraftListener(self))
        self.server.scheduler.run_task(self, self._tracking_tick, delay=0, period=self._interval_ticks)

        bridge_state = "enabled" if self._bridge_enabled else "disabled"
        self.logger.info(
            "VoiceCraft Endstone Phase 2 enabled: "
            f"interval={self._interval_ticks} ticks, Endstone API={self.api_version}, bridge={bridge_state}"
        )
        self.logger.info("Commands ready: /vcbind /vcunbind /vcstatus /vcdump")

        if self._bridge is not None:
            self._bridge.start()
            self.logger.info(
                f"BRIDGE starting outbound WSS client server_id={self._bridge_server_id}; credentials hidden"
            )

        for player in self.server.online_players:
            self._discover_player_if_ready(player, source="enable")

    def on_disable(self) -> None:
        try:
            self.server.scheduler.cancel_tasks(self)
        except Exception as exc:
            self.logger.warning(f"Could not cancel scheduler tasks cleanly: {type(exc).__name__}: {exc}")
        if self._bridge is not None:
            self._bridge.stop()
        self._states.clear()
        self._pending_bind_keys.clear()
        self._pending_bind_requests.clear()
        self._last_movement_log.clear()
        self.logger.info("VoiceCraft Endstone Phase 2 disabled")

    def on_command(self, sender: CommandSender, command: Command, args: list[str]) -> bool:
        if command.name == "vcbind":
            return self._command_bind(sender, args)
        if command.name == "vcunbind":
            return self._command_unbind(sender)
        if command.name == "vcstatus":
            return self._command_status(sender)
        if command.name == "vcdump":
            return self._command_dump(sender)
        return False

    def _load_settings(self) -> None:
        tracking = self.config.get("tracking", {})
        binding = self.config.get("binding", {})
        bridge = self.config.get("bridge", {})

        self._interval_ticks = self._bounded_int(tracking.get("interval_ticks", 2), 1, 20, 2)
        self._position_epsilon = self._bounded_float(tracking.get("position_epsilon", 0.05), 0.001, 10.0, 0.05)
        self._rotation_epsilon = self._bounded_float(tracking.get("rotation_epsilon", 1.0), 0.01, 180.0, 1.0)
        self._log_position_changes = bool(tracking.get("log_position_changes", False))
        heartbeat_seconds = self._bounded_int(tracking.get("heartbeat_seconds", 30), 1, 3600, 30)
        self._heartbeat_ticks = heartbeat_seconds * 20

        self._min_key_length = self._bounded_int(binding.get("min_key_length", 4), 1, 1024, 4)
        self._max_key_length = self._bounded_int(binding.get("max_key_length", 128), self._min_key_length, 4096, 128)

        enabled = bool(bridge.get("enabled", False))
        url = str(bridge.get("url", "")).strip()
        server_id = str(bridge.get("server_id", "mcsv-main")).strip()
        secret = str(bridge.get("secret", "")).strip()
        reconnect_seconds = self._bounded_float(bridge.get("reconnect_seconds", 5), 1.0, 60.0, 5.0)

        placeholders = ("YOUR-RELAY", "CHANGE_ME")
        usable = enabled and url.startswith(("ws://", "wss://")) and server_id and secret
        usable = usable and not any(marker in url or marker in secret for marker in placeholders)
        self._bridge_enabled = usable
        self._bridge_server_id = server_id or "mcsv-main"
        self._bridge = (
            EndstoneRelayClient(self.logger, url, self._bridge_server_id, secret, reconnect_seconds)
            if usable
            else None
        )
        if enabled and not usable:
            self.logger.warning(
                "BRIDGE enabled in config but URL/server_id/secret is incomplete; bridge remains disabled"
            )

    @staticmethod
    def _bounded_int(value: Any, minimum: int, maximum: int, fallback: int) -> int:
        try:
            value = int(value)
        except (TypeError, ValueError):
            return fallback
        return max(minimum, min(maximum, value))

    @staticmethod
    def _bounded_float(value: Any, minimum: float, maximum: float, fallback: float) -> float:
        try:
            value = float(value)
        except (TypeError, ValueError):
            return fallback
        return max(minimum, min(maximum, value))

    @staticmethod
    def _player_key(player: Player) -> str:
        xuid = str(player.xuid or "")
        return xuid if xuid else str(player.unique_id)

    def _resolve_bind_player_key(self, message: dict[str, Any]) -> str:
        """Resolve a bind result to the canonical Endstone player key.

        requestId is authoritative for an in-flight bind because it was
        generated by this Endstone instance. XUID/UUID are fallback identity
        hints from the Android bridge.
        """
        request_id = str(message.get("requestId", "") or "")
        if request_id:
            for player_key, pending_request in tuple(self._pending_bind_requests.items()):
                if pending_request == request_id:
                    return player_key

        xuid = str(message.get("xuid", "") or "")
        uuid_value = str(message.get("uuid", "") or "")

        for player in self.server.online_players:
            try:
                if xuid and str(player.xuid or "") == xuid:
                    return self._player_key(player)
                if uuid_value and str(player.unique_id) == uuid_value:
                    return self._player_key(player)
            except Exception:
                continue

        if xuid:
            if (
                xuid in self._states
                or xuid in self._pending_bind_keys
                or xuid in self._pending_bind_requests
            ):
                return xuid

        if uuid_value:
            for player_key, state in tuple(self._states.items()):
                try:
                    if str(state.uuid) == uuid_value:
                        return player_key
                except Exception:
                    continue

        return xuid or uuid_value

    @staticmethod
    def _snapshot(player: Player) -> PlayerState:
        location = player.location
        return PlayerState(
            name=str(player.name),
            xuid=str(player.xuid or ""),
            uuid=str(player.unique_id),
            dimension=str(player.dimension.name),
            x=float(location.x),
            y=float(location.y),
            z=float(location.z),
            yaw=float(location.yaw),
            pitch=float(location.pitch),
        )

    @staticmethod
    def _valid_state(state: PlayerState) -> bool:
        values = (state.x, state.y, state.z, state.yaw, state.pitch)
        if not all(math.isfinite(value) for value in values):
            return False
        # Endstone/BDS exposes a pre-spawn sentinel around Y=32768. Never let
        # that transitional position reach the VoiceCraft proximity world.
        if state.y < -4096.0 or state.y > 4096.0:
            return False
        if abs(state.x) > 30_000_000 or abs(state.z) > 30_000_000:
            return False
        return bool(state.dimension)

    @staticmethod
    def _fingerprint(secret: str) -> str:
        return hashlib.sha256(secret.encode("utf-8")).hexdigest()[:10]

    @staticmethod
    def _state_message(state: PlayerState) -> dict[str, Any]:
        return {
            "type": "player_state",
            "name": state.name,
            "xuid": state.xuid,
            "uuid": state.uuid,
            "dimension": state.dimension,
            "x": state.x,
            "y": state.y,
            "z": state.z,
            "yaw": state.yaw,
            "pitch": state.pitch,
        }

    def _bridge_send(self, message: dict[str, Any]) -> bool:
        return self._bridge.send(message) if self._bridge is not None else False

    def _discover_player_if_ready(self, player: Player, source: str) -> PlayerState | None:
        try:
            state = self._snapshot(player)
            if not self._valid_state(state):
                return None
            key = self._player_key(player)
            previous = self._states.get(key)
            self._states[key] = state
            if previous is None:
                self.logger.info(f"TRACK DISCOVER {state.compact()} source={source}")
            self._bridge_send(self._state_message(state))
            return state
        except Exception as exc:
            self.logger.warning(f"TRACK DISCOVER failed player={getattr(player, 'name', '?')}: {type(exc).__name__}: {exc}")
            return None

    def handle_player_join(self, player: Player) -> None:
        try:
            state = self._snapshot(player)
            if not self._valid_state(state):
                self.logger.info(
                    f"PLAYER JOIN waiting for valid spawn position name={player.name} xuid={player.xuid}"
                )
                return
            key = self._player_key(player)
            self._states[key] = state
            self.logger.info(f"PLAYER JOIN {state.compact()}")
            self._bridge_send(self._state_message(state))
        except Exception as exc:
            self.logger.error(f"PLAYER JOIN snapshot failed for {player.name}: {type(exc).__name__}: {exc}")

    def handle_player_quit(self, player: Player) -> None:
        key = self._player_key(player)
        state = self._states.pop(key, None)
        self._pending_bind_keys.pop(key, None)
        request_id = self._pending_bind_requests.pop(key, None)
        self._last_movement_log.pop(key, None)
        payload = {
            "type": "player_leave",
            "name": str(player.name),
            "xuid": str(player.xuid or ""),
            "uuid": str(player.unique_id),
        }
        self._bridge_send(payload)
        if state is not None:
            self.logger.info(f"PLAYER QUIT name={state.name} xuid={state.xuid} uuid={state.uuid}")
        else:
            self.logger.info(f"PLAYER QUIT name={player.name} xuid={player.xuid}")
        if request_id:
            self.logger.info(f"BIND pending request cancelled because player left request={request_id[:8]}")

    def _tracking_tick(self) -> None:
        self._drain_bridge_messages()
        self._log_bridge_peer_change()
        current_keys: set[str] = set()

        for player in self.server.online_players:
            try:
                key = self._player_key(player)
                current_keys.add(key)
                current = self._snapshot(player)
                if not self._valid_state(current):
                    # Ignore pre-spawn/transitional state (e.g. Y=32768).
                    continue

                previous = self._states.get(key)
                if previous is None:
                    self._states[key] = current
                    self.logger.info(f"TRACK DISCOVER {current.compact()} source=tick")
                    self._bridge_send(self._state_message(current))
                    continue

                dimension_changed = current.dimension != previous.dimension
                position_changed = current.position_changed(previous, self._position_epsilon)
                rotation_changed = current.rotation_changed(previous, self._rotation_epsilon)
                name_changed = current.name != previous.name

                if dimension_changed:
                    self.logger.info(
                        f"DIMENSION {current.name} xuid={current.xuid} {previous.dimension} -> {current.dimension} "
                        f"pos=({current.x:.2f},{current.y:.2f},{current.z:.2f})"
                    )

                if self._log_position_changes and (position_changed or rotation_changed):
                    now = time.monotonic()
                    if now - self._last_movement_log.get(key, 0.0) >= 1.0:
                        self._last_movement_log[key] = now
                        self.logger.info(f"MOVE {current.compact()}")

                if dimension_changed or position_changed or rotation_changed or name_changed:
                    self._states[key] = current
                    self._bridge_send(self._state_message(current))
            except Exception as exc:
                self.logger.warning(f"TRACK ERROR player={getattr(player, 'name', '?')}: {type(exc).__name__}: {exc}")

        for stale_key in set(self._states).difference(current_keys):
            stale = self._states.pop(stale_key)
            self._pending_bind_keys.pop(stale_key, None)
            self._pending_bind_requests.pop(stale_key, None)
            self._last_movement_log.pop(stale_key, None)
            self._bridge_send(
                {"type": "player_leave", "name": stale.name, "xuid": stale.xuid, "uuid": stale.uuid}
            )
            self.logger.info(f"TRACK REMOVE name={stale.name} xuid={stale.xuid}")

        self._heartbeat_accumulator += self._interval_ticks
        if self._heartbeat_accumulator >= self._heartbeat_ticks:
            self._heartbeat_accumulator = 0
            pending = sum(1 for key in current_keys if key in self._pending_bind_keys)
            bridge_status = self._bridge_status_text()
            self.logger.info(
                f"HEARTBEAT online={len(current_keys)} tracked={len(self._states)} "
                f"pending_bindings={pending} bridge={bridge_status}"
            )
            self._bridge_send(
                {
                    "type": "heartbeat",
                    "online": len(current_keys),
                    "tracked": len(self._states),
                    "pendingBindings": pending,
                }
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

    def _send_full_snapshot(self) -> None:
        self._bridge_send({"type": "sync_begin", "count": len(self._states)})
        for state in self._states.values():
            self._bridge_send(self._state_message(state))
        self._bridge_send({"type": "sync_end", "count": len(self._states)})
        self.logger.info(f"BRIDGE snapshot queued players={len(self._states)}")

    def _handle_bind_result(self, message: dict[str, Any]) -> None:
        request_id = str(message.get("requestId", "") or "")
        xuid = str(message.get("xuid", "") or "")
        uuid_value = str(message.get("uuid", "") or "")
        success = bool(message.get("success", False))
        reason = str(message.get("reason", ""))[:160]

        player_key = self._resolve_bind_player_key(message)
        if player_key:
            self._pending_bind_keys.pop(player_key, None)
            if self._pending_bind_requests.get(player_key) == request_id:
                self._pending_bind_requests.pop(player_key, None)

        target = None
        if player_key:
            target = next(
                (
                    p for p in self.server.online_players
                    if self._player_key(p) == player_key
                ),
                None,
            )
        if target is None:
            target = next(
                (
                    p for p in self.server.online_players
                    if (xuid and str(p.xuid or "") == xuid)
                    or (uuid_value and str(p.unique_id) == uuid_value)
                ),
                None,
            )

        if target is not None:
            if success:
                target.send_message("VoiceCraft: successfully bound to your voice client.")
            else:
                target.send_error_message(
                    f"VoiceCraft bind failed: {reason or 'binding key not found'}"
                )

        self.logger.info(
            f"BIND RESULT player_key={player_key[:12] if player_key else '?'} "
            f"xuid={xuid or '?'} request={request_id[:8] or '?'} "
            f"success={success} reason={reason or '-'}"
        )

    def _log_bridge_peer_change(self) -> None:
        if self._bridge is None:
            return
        state = (self._bridge.connected, self._bridge.android_connected)
        if state == self._last_peer_state:
            return
        self._last_peer_state = state
        self.logger.info(
            f"BRIDGE STATUS relay={'connected' if state[0] else 'disconnected'} "
            f"android={'connected' if state[1] else 'disconnected'}"
        )
        if state == (True, True):
            self._send_full_snapshot()

    def _bridge_status_text(self) -> str:
        if self._bridge is None:
            return "disabled"
        if not self._bridge.connected:
            return "relay-disconnected"
        return "android-connected" if self._bridge.android_connected else "relay-only"

    def _command_bind(self, sender: CommandSender, args: list[str]) -> bool:
        if not isinstance(sender, Player):
            sender.send_error_message("/vcbind must be run by a player.")
            return False
        if len(args) != 1:
            sender.send_error_message("Usage: /vcbind <key>")
            return False

        key_value = args[0].strip()
        if not (self._min_key_length <= len(key_value) <= self._max_key_length):
            sender.send_error_message(
                f"Binding key length must be {self._min_key_length}-{self._max_key_length} characters."
            )
            return False

        player_key = self._player_key(sender)
        state = self._states.get(player_key)
        if state is None:
            state = self._discover_player_if_ready(sender, source="bind")
        if state is None:
            sender.send_error_message("VoiceCraft cannot bind until your spawn position is ready. Try again in a moment.")
            return False

        self._pending_bind_keys[player_key] = key_value
        request_id = uuid.uuid4().hex
        self._pending_bind_requests[player_key] = request_id
        fingerprint = self._fingerprint(key_value)
        queued = self._bridge_send(
            {
                "type": "bind",
                "requestId": request_id,
                "bindingKey": key_value,
                **{k: v for k, v in self._state_message(state).items() if k != "type"},
            }
        )

        self.logger.info(
            f"BIND CAPTURED player={sender.name} xuid={sender.xuid} key_fingerprint={fingerprint} "
            f"request={request_id[:8]} bridge={self._bridge_status_text()} queued={queued}"
        )

        if self._bridge is None:
            sender.send_message("VoiceCraft binding key captured, but Phase 2 bridge is disabled in config.toml.")
        elif queued:
            sender.send_message("VoiceCraft binding request sent to the mobile server bridge.")
        else:
            sender.send_error_message("VoiceCraft bridge queue is unavailable; try again shortly.")
        return True

    def _command_unbind(self, sender: CommandSender) -> bool:
        if not isinstance(sender, Player):
            sender.send_error_message("/vcunbind must be run by a player.")
            return False
        player_key = self._player_key(sender)
        removed = self._pending_bind_keys.pop(player_key, None)
        self._pending_bind_requests.pop(player_key, None)
        if removed is None:
            sender.send_message("No pending VoiceCraft binding request was stored.")
        else:
            self.logger.info(f"BIND CLEARED player={sender.name} xuid={sender.xuid}")
            sender.send_message("Pending VoiceCraft binding request cleared.")
        return True

    def _command_status(self, sender: CommandSender) -> bool:
        online = len(self.server.online_players)
        sender.send_message(
            f"VoiceCraft Endstone v{self.version}: Phase 2 tracker active, bridge={self._bridge_status_text()}, "
            f"online={online}, tracked={len(self._states)}, interval={self._interval_ticks} ticks"
        )
        if isinstance(sender, Player):
            key = self._player_key(sender)
            state = self._states.get(key)
            if state is None:
                try:
                    candidate = self._snapshot(sender)
                    state = candidate if self._valid_state(candidate) else None
                except Exception:
                    state = None
            if state is not None:
                sender.send_message(
                    f"You: dim={state.dimension} pos=({state.x:.2f}, {state.y:.2f}, {state.z:.2f}) "
                    f"yaw={state.yaw:.1f} pitch={state.pitch:.1f}"
                )
            sender.send_message("Pending binding: " + ("yes" if key in self._pending_bind_keys else "no"))
        return True

    def _command_dump(self, sender: CommandSender) -> bool:
        if not self._states:
            sender.send_message("VoiceCraft tracker has no valid player states.")
            return True
        sender.send_message(f"VoiceCraft tracked states ({len(self._states)}):")
        for state in sorted(self._states.values(), key=lambda item: item.name.lower()):
            sender.send_message(state.compact())
        return True
