from __future__ import annotations

import json
from typing import Any

from endstone import Player
from endstone.form import ModalForm, TextInput

from .compat import VoiceCraftEndstone as VoiceCraftEndstone021


class VoiceCraftEndstone(VoiceCraftEndstone021):
    """Endstone 0.2.2: automatic in-game binding form for unbound players."""

    version = "0.2.2"

    _AUTO_FORM_DELAY_TICKS = 20
    _AUTO_FORM_RETRY_TICKS = 10

    def __init__(self) -> None:
        super().__init__()
        self._auto_bind_scheduled: set[str] = set()
        self._auto_bind_shown: set[str] = set()
        self._bound_players: set[str] = set()

    def on_disable(self) -> None:
        self._auto_bind_scheduled.clear()
        self._auto_bind_shown.clear()
        self._bound_players.clear()
        super().on_disable()

    def handle_player_join(self, player: Player) -> None:
        player_key = self._player_key(player)
        # Android currently releases the binding when Endstone reports
        # player_leave, so every real re-join starts unbound until a new bind
        # succeeds. Do not retain stale local state across sessions.
        self._bound_players.discard(player_key)
        self._auto_bind_shown.discard(player_key)

        super().handle_player_join(player)
        self._schedule_auto_bind_form(player_key, self._AUTO_FORM_DELAY_TICKS)

    def handle_player_quit(self, player: Player) -> None:
        player_key = self._player_key(player)
        self._auto_bind_scheduled.discard(player_key)
        self._auto_bind_shown.discard(player_key)
        self._bound_players.discard(player_key)
        super().handle_player_quit(player)

    def _handle_bind_result(self, message: dict[str, Any]) -> None:
        player_key = self._resolve_bind_player_key(message)
        success = bool(message.get("success", False))

        super()._handle_bind_result(message)

        if not player_key:
            return

        if success:
            self._bound_players.add(player_key)
            self._auto_bind_scheduled.discard(player_key)
            self._auto_bind_shown.add(player_key)
            return

        # A wrong/expired key should take the player back to the form instead
        # of forcing them to type the command manually.
        self._bound_players.discard(player_key)
        self._auto_bind_shown.discard(player_key)
        self._schedule_auto_bind_form(player_key, self._AUTO_FORM_RETRY_TICKS)

    def _schedule_auto_bind_form(self, player_key: str, delay: int) -> None:
        if not player_key:
            return
        if player_key in self._bound_players:
            return
        if player_key in self._pending_bind_keys:
            return
        if player_key in self._auto_bind_scheduled:
            return
        if player_key in self._auto_bind_shown:
            return

        self._auto_bind_scheduled.add(player_key)

        def callback() -> None:
            self._auto_bind_scheduled.discard(player_key)
            self._show_auto_bind_form(player_key)

        try:
            self.server.scheduler.run_task(self, callback, delay=max(1, int(delay)))
        except Exception as exc:
            self._auto_bind_scheduled.discard(player_key)
            self.logger.warning(
                f"BIND FORM schedule failed player_key={player_key[:12]}: {type(exc).__name__}: {exc}"
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
                f"BIND FORM snapshot failed player={getattr(player, 'name', '?')}: {type(exc).__name__}: {exc}"
            )
            self._schedule_auto_bind_form(player_key, self._AUTO_FORM_RETRY_TICKS)
            return

        # Bedrock can fire PlayerJoinEvent before the final spawn position is
        # ready. Never open the form while the player is still in that
        # transitional state; retry shortly instead.
        if not self._valid_state(state):
            self._schedule_auto_bind_form(player_key, self._AUTO_FORM_RETRY_TICKS)
            return

        if player_key not in self._states:
            self._states[player_key] = state
            self._bridge_send(self._state_message(state))

        self._auto_bind_shown.add(player_key)
        form = ModalForm(
            title="VoiceCraft - Bind Microphone",
            controls=[
                TextInput(
                    label="กรอก Binding Key ที่แสดงใน VoiceCraft Client เพื่อเชื่อมไมค์กับตัวละครของคุณ",
                    placeholder="Binding Key เช่น Ab3X9",
                )
            ],
            submit_button="Bind",
            on_submit=self._on_auto_bind_submit,
            on_close=self._on_auto_bind_close,
        )

        try:
            player.send_form(form)
            self.logger.info(f"BIND FORM shown player={player.name} xuid={player.xuid}")
        except Exception as exc:
            self._auto_bind_shown.discard(player_key)
            self.logger.warning(
                f"BIND FORM send failed player={player.name}: {type(exc).__name__}: {exc}"
            )
            self._schedule_auto_bind_form(player_key, self._AUTO_FORM_RETRY_TICKS)

    def _on_auto_bind_submit(self, player: Player, response: Any) -> None:
        player_key = self._player_key(player)
        if player_key in self._bound_players:
            return

        binding_key = self._extract_binding_key(response)
        if not binding_key:
            player.send_error_message("กรุณากรอก Binding Key ก่อนกด Bind")
            self._auto_bind_shown.discard(player_key)
            self._schedule_auto_bind_form(player_key, self._AUTO_FORM_RETRY_TICKS)
            return

        accepted = self._command_bind(player, [binding_key])
        if accepted:
            return

        self._auto_bind_shown.discard(player_key)
        self._schedule_auto_bind_form(player_key, self._AUTO_FORM_RETRY_TICKS)

    def _on_auto_bind_close(self, player: Player) -> None:
        player_key = self._player_key(player)
        if player_key in self._bound_players or player_key in self._pending_bind_keys:
            return

        player.send_error_message(
            "คุณยังไม่ได้ Bind จึงไม่สามารถใช้ไมค์ได้ สามารถใช้ /vcbind <key> เพื่อ Bind ภายหลังได้"
        )
        self.logger.info(f"BIND FORM closed unbound player={player.name} xuid={player.xuid}")

    def _find_online_player(self, player_key: str) -> Player | None:
        for player in self.server.online_players:
            try:
                if self._player_key(player) == player_key:
                    return player
            except Exception:
                continue
        return None

    @staticmethod
    def _extract_binding_key(response: Any) -> str:
        data = response
        if isinstance(data, str):
            text = data.strip()
            if not text:
                return ""
            try:
                data = json.loads(text)
            except (TypeError, ValueError, json.JSONDecodeError):
                return text

        if isinstance(data, (list, tuple)) and data:
            value = data[0]
            return "" if value is None else str(value).strip()

        if isinstance(data, dict):
            for key in ("bindingKey", "binding_key", "0"):
                if key in data and data[key] is not None:
                    return str(data[key]).strip()

        return ""
