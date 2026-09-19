from __future__ import annotations

from typing import Any

from endstone import Player

from .voice_range import VoiceCraftEndstone as VoiceCraftEndstone028


BIND_DDUI_READY_TAG = "voicecraft.bind.ddui.ready"
BIND_STATE_PREFIX = "voicecraft.bind.state."
BIND_OPEN_PREFIX = "voicecraft.bind.open."
BIND_REQUEST_PREFIX = "voicecraft.bind.request."
BIND_ERROR_PREFIX = "voicecraft.bind.error."
BIND_UI_CLOSED_PREFIX = "voicecraft.bind.ui.closed."
BIND_UI_REQUEST_PREFIX = "voicecraft.bind.ui.request."

STATE_UNBOUND = "unbound"
STATE_PENDING = "pending"
STATE_BOUND = "bound"
STATE_RECONNECTING = "reconnecting"
STATE_REBIND_REQUIRED = "rebind_required"
STATE_ERROR = "error"
STATE_DISCONNECTING = "disconnecting"


class VoiceCraftEndstone(VoiceCraftEndstone028):
    """Endstone 0.2.13: direct Mic Bind support with concise reconnect messages."""

    prefix = "VoiceCraftEndstone"
    version = "0.2.13"
    api_version = "0.11"
    description = (
        "VoiceCraft binding, direct Mic Bind, explicit reconnect/rebind state, failover, "
        "Item Mic and per-player voice range"
    )
    authors = ["SamSoSleepy"]

    commands = {
        "vc": {
            "description": "Open the VoiceCraft control menu",
            "usages": ["/vc"],
            "permissions": ["voicecraft.command.menu"],
        }
    }
    permissions = {
        "voicecraft.command.menu": {"description": "Open VoiceCraft menu.", "default": True},
        "voicecraft.command.bind": {"description": "Bind/unbind VoiceCraft.", "default": True},
        "voicecraft.command.status": {"description": "View VoiceCraft status.", "default": True},
        "voicecraft.command.dump": {"description": "View tracked players.", "default": "op"},
        "voicecraft.command.voice_range_admin": {
            "description": "Change maximum voice range.",
            "default": "op",
        },
        "voicecraft.command.voice_range_unlimited": {
            "description": "Bypass maximum voice range.",
            "default": "op",
        },
    }

    def __init__(self) -> None:
        super().__init__()
        self._bind_open_sequence = 0

    def on_enable(self) -> None:
        super().on_enable()
        self.server.scheduler.run_task(self, self._bind_ddui_tick, delay=1, period=2)
        for player in self.server.online_players:
            self._publish_derived_bind_state(player)
        self.logger.info(
            "VoiceCraft direct-Mic DDUI bind bridge ready; addon handshake="
            f"{BIND_DDUI_READY_TAG}; ModalForm fallback retained"
        )

    def handle_player_join(self, player: Player) -> None:
        player_key = self._player_key(player)

        # Treat every real Minecraft join as a fresh DDUI binding session.
        # VoiceCraft Server releases the entity binding on player_leave, so a
        # returning player must receive a new Binding Key form even if stale
        # scoreboard UI tags survived the previous session.
        self._rebind_waiting.discard(player_key)
        self._auto_bind_shown.discard(player_key)
        self._remove_prefixed_tags(
            player,
            BIND_STATE_PREFIX,
            BIND_OPEN_PREFIX,
            BIND_REQUEST_PREFIX,
            BIND_ERROR_PREFIX,
            BIND_UI_CLOSED_PREFIX,
            BIND_UI_REQUEST_PREFIX,
            BIND_DDUI_READY_TAG,
        )

        super().handle_player_join(player)
        self._publish_bind_state(player, STATE_UNBOUND)

    def handle_player_quit(self, player: Player) -> None:
        player_key = self._player_key(player)
        self._rebind_waiting.discard(player_key)
        self._auto_bind_shown.discard(player_key)
        self._remove_prefixed_tags(
            player,
            BIND_STATE_PREFIX,
            BIND_OPEN_PREFIX,
            BIND_REQUEST_PREFIX,
            BIND_ERROR_PREFIX,
            BIND_UI_CLOSED_PREFIX,
            BIND_DDUI_READY_TAG,
        )
        super().handle_player_quit(player)

    def _has_bind_ddui(self, player: Player) -> bool:
        try:
            return BIND_DDUI_READY_TAG in set(player.scoreboard_tags)
        except Exception:
            return False

    @staticmethod
    def _remove_prefixed_tags(player: Player, *prefixes: str) -> None:
        try:
            tags = tuple(player.scoreboard_tags)
        except Exception:
            return
        for tag in tags:
            if any(tag.startswith(prefix) for prefix in prefixes):
                try:
                    player.remove_scoreboard_tag(tag)
                except Exception:
                    pass

    def _publish_bind_state(
        self,
        player: Player,
        state: str,
        *,
        open_ui: bool = False,
        error: str | None = None,
    ) -> None:
        self._remove_prefixed_tags(
            player,
            BIND_STATE_PREFIX,
            BIND_ERROR_PREFIX,
            BIND_OPEN_PREFIX,
        )
        player.add_scoreboard_tag(f"{BIND_STATE_PREFIX}{state}")
        if error:
            safe_error = "".join(ch for ch in error.lower() if ch.isalnum() or ch in "_-")[:48]
            if safe_error:
                player.add_scoreboard_tag(f"{BIND_ERROR_PREFIX}{safe_error}")
        if open_ui:
            self._bind_open_sequence = (self._bind_open_sequence + 1) % 2_000_000_000
            player.add_scoreboard_tag(f"{BIND_OPEN_PREFIX}{self._bind_open_sequence}")

    def _publish_derived_bind_state(self, player: Player) -> None:
        player_key = self._player_key(player)
        if player_key in self._pending_unbind_requests:
            state = STATE_DISCONNECTING
        elif player_key in self._bound_players:
            state = STATE_BOUND
        elif player_key in self._pending_bind_keys:
            state = STATE_PENDING
        elif player_key in self._rebind_waiting:
            state = STATE_RECONNECTING
        else:
            state = STATE_UNBOUND

        try:
            if any(tag.startswith(BIND_STATE_PREFIX) for tag in player.scoreboard_tags):
                return
        except Exception:
            pass
        self._publish_bind_state(player, state)

    def _request_bind_ui(
        self,
        player_key: str,
        *,
        state: str,
        error: str | None = None,
        source: str = "server",
        allow_fallback: bool = True,
    ) -> bool:
        """Issue one fresh Bind UI request from any entry path."""
        if not player_key:
            return False
        if player_key in self._bound_players:
            return False
        if player_key in self._pending_bind_keys:
            return False
        if player_key in self._pending_unbind_requests:
            return False

        player = self._find_online_player(player_key)
        if player is None:
            return False

        # UI visibility is not connection state. Always release the old UI
        # latch before producing a fresh DDUI open token.
        self._auto_bind_shown.discard(player_key)
        self._remove_prefixed_tags(
            player,
            BIND_OPEN_PREFIX,
            BIND_UI_CLOSED_PREFIX,
            BIND_UI_REQUEST_PREFIX,
        )

        if self._has_bind_ddui(player):
            self._publish_bind_state(player, state, open_ui=True, error=error)
            self._auto_bind_shown.add(player_key)
            self.logger.info(
                f"BIND DDUI request player={player.name} state={state} source={source}"
            )
            return True

        if not allow_fallback:
            return False

        # Addon is optional; keep the original Endstone form as fallback.
        super()._show_auto_bind_form(player_key)
        return True

    def _open_bind_ui_or_fallback(
        self,
        player_key: str,
        *,
        state: str,
        error: str | None = None,
    ) -> None:
        self._request_bind_ui(
            player_key,
            state=state,
            error=error,
            source="auto_join",
        )

    def _show_auto_bind_form(self, player_key: str) -> None:
        if player_key in self._bound_players or player_key in self._pending_bind_keys:
            return
        if player_key in self._auto_bind_shown:
            return

        player = self._find_online_player(player_key)
        if player is None:
            return

        try:
            state = self._snapshot(player)
        except Exception as exc:
            self.logger.warning(
                f"BIND DDUI snapshot failed player={getattr(player, 'name', '?')}: "
                f"{type(exc).__name__}: {exc}"
            )
            self._schedule_auto_bind_form(player_key, self._AUTO_FORM_RETRY_TICKS)
            return

        if not self._valid_state(state):
            self._schedule_auto_bind_form(player_key, self._AUTO_FORM_RETRY_TICKS)
            return

        if player_key not in self._states:
            self._states[player_key] = state
            self._bridge_send(self._state_message(state))

        self._open_bind_ui_or_fallback(player_key, state=STATE_UNBOUND)

    def _menu_bind(self, player: Player) -> None:
        if not player.has_permission("voicecraft.command.bind"):
            player.send_error_message("You do not have permission to bind VoiceCraft.")
            return

        player_key = self._player_key(player)
        if player_key in self._bound_players:
            player.send_message("VoiceCraft is already bound to your current voice client.")
            self._publish_bind_state(player, STATE_BOUND)
            return
        if player_key in self._pending_bind_keys:
            player.send_message("A VoiceCraft binding request is already pending.")
            self._publish_bind_state(player, STATE_PENDING)
            return
        if player_key in self._pending_unbind_requests:
            player.send_message("VoiceCraft disconnect is still in progress.")
            self._publish_bind_state(player, STATE_DISCONNECTING)
            return

        if player_key in self._rebind_waiting:
            if self._has_bind_ddui(player):
                self._request_bind_ui(
                    player_key,
                    state=STATE_RECONNECTING,
                    source="vc_menu_reconnecting",
                )
                return
            player.send_message(
                "§e[ViceCraft] หลุดการเชื่อมต่อ กำลังเชื่อมต่อใหม่§r"
            )
            return

        if self._has_bind_ddui(player):
            self._request_bind_ui(
                player_key,
                state=STATE_UNBOUND,
                source="vc_menu",
            )
            return

        super()._menu_bind(player)

    @staticmethod
    def _bind_error_code(message: dict[str, Any]) -> str:
        reason = str(message.get("reason", "")).lower()
        if "not found" in reason or "already used" in reason:
            return "invalid_key"
        if "no longer exists" in reason:
            return "client_disconnected"
        if "server positioning" in reason:
            return "server_mode_required"
        return "rejected"

    def _handle_bind_result(self, message: dict[str, Any]) -> None:
        player_key = str(message.get("xuid", "") or message.get("uuid", ""))
        success = bool(message.get("success", False))

        super()._handle_bind_result(message)

        if not player_key:
            return
        player = self._find_online_player(player_key)
        if player is None:
            return

        if success:
            self._rebind_waiting.discard(player_key)
            self._publish_bind_state(player, STATE_BOUND)
            return

        if self._has_bind_ddui(player):
            self._request_bind_ui(
                player_key,
                state=STATE_ERROR,
                error=self._bind_error_code(message),
                source="bind_error",
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
                f"VOICE DISCONNECT manual-unbind race suppressed "
                f"player_key={player_key[:12]} entity={disconnected_entity}"
            )
            return
        if (
            disconnected_entity is not None
            and disconnected_entity in self._manual_unbound_entities
        ):
            self._manual_unbound_entities.discard(disconnected_entity)
            self.logger.info(
                f"VOICE DISCONNECT post-unbind stale event suppressed "
                f"player_key={player_key[:12]} entity={disconnected_entity}"
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

        self._publish_bind_state(player, STATE_RECONNECTING)
        player.send_message(
            "§e[ViceCraft] หลุดการเชื่อมต่อ กำลังเชื่อมต่อใหม่§r"
        )
        self.logger.info(
            f"VOICE DISCONNECT player={player.name} xuid={player.xuid}; "
            "auto reconnect grace=5s"
        )

        def callback() -> None:
            self._rebind_waiting.discard(player_key)
            if player_key in self._bound_players or player_key in self._pending_bind_keys:
                return
            online = self._find_online_player(player_key)
            if online is None:
                return

            self._auto_bind_shown.discard(player_key)
            self._publish_bind_state(
                online,
                STATE_REBIND_REQUIRED,
            )
            online.send_message(
                "§e[ViceCraft] ไม่สามารถเชื่อมต่อได้ใช้ไอเทมไมค์เพื่อเชื่อมต่ออีกครั้ง§r"
            )

        try:
            self.server.scheduler.run_task(
                self,
                callback,
                delay=self._RECONNECT_FORM_DELAY_TICKS,
            )
        except Exception as exc:
            self._rebind_waiting.discard(player_key)
            self.logger.warning(
                f"REBIND DDUI schedule failed player_key={player_key[:12]}: "
                f"{type(exc).__name__}: {exc}"
            )
            self._schedule_auto_bind_form(
                player_key,
                self._RECONNECT_FORM_DELAY_TICKS,
            )

    def _handle_unbind_result(self, message: dict[str, Any]) -> None:
        player_key = str(message.get("xuid", "") or message.get("uuid", ""))
        success = bool(message.get("success", False))
        super()._handle_unbind_result(message)

        if not player_key:
            return
        player = self._find_online_player(player_key)
        if player is None:
            return
        if success:
            self._auto_bind_shown.discard(player_key)
            self._publish_bind_state(player, STATE_UNBOUND)
        elif player_key in self._bound_players:
            self._publish_bind_state(player, STATE_BOUND)

    def _bind_ddui_tick(self) -> None:
        for player in self.server.online_players:
            try:
                tags = tuple(player.scoreboard_tags)
                player_key = self._player_key(player)

                closed_events = [
                    tag for tag in tags if tag.startswith(BIND_UI_CLOSED_PREFIX)
                ]
                if closed_events:
                    for tag in closed_events:
                        player.remove_scoreboard_tag(tag)

                    # A client-side X dismissal must release the Endstone UI
                    # latch so /vc can request another DDUI immediately. Do
                    # not reopen automatically; the player explicitly closed
                    # it. Pending/bound states remain authoritative.
                    self._auto_bind_shown.discard(player_key)
                    if (
                        player_key not in self._bound_players
                        and player_key not in self._pending_bind_keys
                        and player_key not in self._rebind_waiting
                    ):
                        self._publish_bind_state(player, STATE_UNBOUND)
                    self.logger.info(
                        f"BIND DDUI closed by player={player.name}; reopen available via /vc"
                    )
                    tags = tuple(player.scoreboard_tags)

                ui_requests = [
                    tag for tag in tags if tag.startswith(BIND_UI_REQUEST_PREFIX)
                ]
                if ui_requests:
                    request_source = "addon"
                    for tag in ui_requests:
                        value = tag[len(BIND_UI_REQUEST_PREFIX):].strip()
                        if value:
                            request_source = value[:32]
                        player.remove_scoreboard_tag(tag)

                    if player_key in self._bound_players:
                        self._publish_bind_state(player, STATE_BOUND)
                    elif player_key in self._pending_bind_keys:
                        self._publish_bind_state(player, STATE_PENDING)
                    elif player_key in self._pending_unbind_requests:
                        self._publish_bind_state(player, STATE_DISCONNECTING)
                    elif player_key in self._rebind_waiting:
                        self._publish_bind_state(player, STATE_RECONNECTING)
                    else:
                        current_state = STATE_UNBOUND
                        try:
                            for tag in player.scoreboard_tags:
                                if tag.startswith(BIND_STATE_PREFIX):
                                    candidate = tag[len(BIND_STATE_PREFIX):]
                                    if candidate in (
                                        STATE_UNBOUND,
                                        STATE_REBIND_REQUIRED,
                                        STATE_ERROR,
                                    ):
                                        current_state = candidate
                                    break
                        except Exception:
                            pass
                        self._request_bind_ui(
                            player_key,
                            state=current_state,
                            source=f"addon_{request_source}",
                        )
                    tags = tuple(player.scoreboard_tags)

                requests = [
                    tag for tag in tags if tag.startswith(BIND_REQUEST_PREFIX)
                ]
                if not requests:
                    self._publish_derived_bind_state(player)
                    continue

                binding_key = ""
                for tag in requests:
                    value = tag[len(BIND_REQUEST_PREFIX):].strip()
                    if value:
                        binding_key = value
                    player.remove_scoreboard_tag(tag)

                if player_key in self._bound_players:
                    self._publish_bind_state(player, STATE_BOUND)
                    continue
                if player_key in self._pending_bind_keys:
                    self._publish_bind_state(player, STATE_PENDING)
                    continue

                if not binding_key:
                    self._publish_bind_state(
                        player,
                        STATE_ERROR,
                        open_ui=True,
                        error="empty_key",
                    )
                    continue

                if not (
                    self._min_key_length
                    <= len(binding_key)
                    <= self._max_key_length
                ):
                    self._publish_bind_state(
                        player,
                        STATE_ERROR,
                        open_ui=True,
                        error="invalid_length",
                    )
                    continue

                self._rebind_waiting.discard(player_key)
                accepted = self._command_bind(player, [binding_key])
                if accepted and player_key in self._pending_bind_keys:
                    self._publish_bind_state(player, STATE_PENDING)
                elif not accepted:
                    self._publish_bind_state(
                        player,
                        STATE_ERROR,
                        open_ui=True,
                        error="rejected",
                    )
            except Exception as exc:
                self.logger.warning(
                    f"BIND DDUI tick failed player={getattr(player, 'name', '?')}: "
                    f"{type(exc).__name__}: {exc}"
                )
