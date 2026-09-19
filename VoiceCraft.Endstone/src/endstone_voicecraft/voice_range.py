from __future__ import annotations

import json
from pathlib import Path

from endstone import Player
from endstone.form import ActionForm, ModalForm, TextInput

from .item_mic import VoiceCraftEndstone as VoiceCraftEndstone027

DEFAULT_RANGE = 20
DEFAULT_MAX = 150
MIN_RANGE = 1
TECH_MAX = 30_000_000
VALUE_PREFIX = "voicecraft.vr.value."
REQUEST_PREFIX = "voicecraft.vr.request."
MAX_PREFIX = "voicecraft.vr.max."
ACK_PREFIX = "voicecraft.vr.ack."
SYNC_PREFIX = "voicecraft.vr.sync."


class VoiceCraftEndstone(VoiceCraftEndstone027):
    """Endstone 0.2.8: /vc registration + outgoing microphone range."""

    prefix = "VoiceCraftEndstone"
    version = "0.2.8"
    api_version = "0.11"
    description = "VoiceCraft binding, failover, Item Mic and per-player voice range"
    authors = ["SamSoSleepy"]

    # Keep command metadata on the final entry-point class so /vc is always
    # registered even when another feature subclasses the menu implementation.
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
        "voicecraft.command.voice_range_admin": {"description": "Change maximum voice range.", "default": "op"},
        "voicecraft.command.voice_range_unlimited": {"description": "Bypass maximum voice range.", "default": "op"},
    }

    def __init__(self) -> None:
        super().__init__()
        self._voice_ranges: dict[str, int] = {}
        self._voice_range_default = DEFAULT_RANGE
        self._voice_range_max = DEFAULT_MAX

    @property
    def _range_store(self) -> Path:
        return self.data_folder / "voice_ranges.json"

    def on_enable(self) -> None:
        self.save_default_config()
        cfg = self.reload_config().get("voice_range", {})
        if not isinstance(cfg, dict):
            cfg = {}
        self._voice_range_default = self._bounded(cfg.get("default_blocks", DEFAULT_RANGE), DEFAULT_RANGE)
        self._voice_range_max = self._bounded(cfg.get("max_blocks", DEFAULT_MAX), DEFAULT_MAX)
        self._voice_range_default = min(self._voice_range_default, self._voice_range_max)
        self._load_ranges()
        super().on_enable()
        self.server.scheduler.run_task(self, self._voice_range_tick, delay=1, period=2)
        for player in self.server.online_players:
            self._sync_player(player, emit=False)
        self.logger.info(
            f"Voice range ready default={self._voice_range_default} max={self._voice_range_max}; /vc registered"
        )

    @staticmethod
    def _bounded(value, fallback: int) -> int:
        try:
            value = int(value)
        except (TypeError, ValueError):
            return fallback
        return max(MIN_RANGE, min(TECH_MAX, value))

    def _load_ranges(self) -> None:
        try:
            if not self._range_store.exists():
                return
            raw = json.loads(self._range_store.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                return
            loaded: dict[str, int] = {}
            for key, value in raw.items():
                try:
                    parsed = int(value)
                except (TypeError, ValueError):
                    continue
                key = str(key)
                if key and MIN_RANGE <= parsed <= TECH_MAX:
                    loaded[key] = parsed
            self._voice_ranges = loaded
        except Exception as exc:
            self.logger.warning(f"VOICE RANGE store load failed: {type(exc).__name__}: {exc}")

    def _save_ranges(self) -> None:
        try:
            self.data_folder.mkdir(parents=True, exist_ok=True)
            tmp = self._range_store.with_suffix(".tmp")
            tmp.write_text(json.dumps(self._voice_ranges, indent=2, sort_keys=True), encoding="utf-8")
            tmp.replace(self._range_store)
        except Exception as exc:
            self.logger.warning(f"VOICE RANGE store save failed: {type(exc).__name__}: {exc}")

    def _unlimited(self, player: Player) -> bool:
        return player.has_permission("voicecraft.command.voice_range_unlimited")

    def _admin(self, player: Player) -> bool:
        return player.has_permission("voicecraft.command.voice_range_admin")

    def _current_range(self, player: Player) -> int:
        key = self._player_key(player)
        value = self._bounded(self._voice_ranges.get(key, self._voice_range_default), self._voice_range_default)
        if not self._unlimited(player) and value > self._voice_range_max:
            value = self._voice_range_max
            self._voice_ranges[key] = value
            self._save_ranges()
        return value

    def _state_message(self, state):
        message = super()._state_message(state)
        key = state.xuid or state.uuid
        message["voiceRange"] = self._bounded(
            self._voice_ranges.get(key, self._voice_range_default), self._voice_range_default
        )
        return message

    def handle_player_join(self, player: Player) -> None:
        super().handle_player_join(player)
        self._remove_range_protocol_tags(
            player,
            REQUEST_PREFIX,
            ACK_PREFIX,
            SYNC_PREFIX,
        )
        self._sync_player(player, emit=True)

    @staticmethod
    def _remove_range_protocol_tags(player: Player, *prefixes: str) -> None:
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

    @staticmethod
    def _safe_range_request_id(value: str) -> str:
        return "".join(ch for ch in str(value) if ch.isalnum() or ch in "_-")[:48]

    def _publish_range_ack(
        self,
        player: Player,
        request_id: str,
        status: str,
        value: int,
    ) -> None:
        request_id = self._safe_range_request_id(request_id)
        if not request_id:
            return
        safe_status = "".join(
            ch for ch in str(status).lower() if ch.isalnum() or ch in "_-"
        )[:16] or "error"
        actual = self._current_range(player)
        try:
            actual = int(value)
        except (TypeError, ValueError):
            pass
        actual = max(MIN_RANGE, min(TECH_MAX, actual))

        ack_prefix = f"{ACK_PREFIX}{request_id}."
        self._remove_range_protocol_tags(player, ack_prefix)
        player.add_scoreboard_tag(
            f"{ACK_PREFIX}{request_id}.{safe_status}.{actual}"
        )

    def _voice_range_tick(self) -> None:
        for player in self.server.online_players:
            try:
                tags = tuple(player.scoreboard_tags)

                sync_requests = [
                    tag for tag in tags if tag.startswith(SYNC_PREFIX)
                ]
                for tag in sync_requests:
                    request_id = self._safe_range_request_id(
                        tag[len(SYNC_PREFIX):].strip()
                    )
                    player.remove_scoreboard_tag(tag)
                    self._sync_player(player, emit=False)
                    if request_id:
                        self._publish_range_ack(
                            player,
                            request_id,
                            "sync",
                            self._current_range(player),
                        )

                requests = [
                    tag for tag in tags if tag.startswith(REQUEST_PREFIX)
                ]
                for tag in requests:
                    payload = tag[len(REQUEST_PREFIX):].strip()
                    player.remove_scoreboard_tag(tag)

                    request_id = ""
                    raw_value = payload
                    if "." in payload:
                        request_id, raw_value = payload.split(".", 1)
                        request_id = self._safe_range_request_id(request_id)

                    try:
                        requested = int(raw_value)
                    except ValueError:
                        requested = None

                    if requested is None:
                        if request_id:
                            self._publish_range_ack(
                                player,
                                request_id,
                                "error",
                                self._current_range(player),
                            )
                        continue

                    success = self._set_range(
                        player,
                        requested,
                        announce=True,
                    )
                    if request_id:
                        self._publish_range_ack(
                            player,
                            request_id,
                            "ok" if success else "error",
                            self._current_range(player),
                        )

                self._sync_player(player, emit=False)
            except Exception as exc:
                self.logger.warning(
                    f"VOICE RANGE tick failed player={player.name}: "
                    f"{type(exc).__name__}: {exc}"
                )

    def _set_range(self, player: Player, value: int, announce: bool) -> bool:
        if value < MIN_RANGE or value > TECH_MAX:
            player.send_error_message(f"[VoiceCraft] ระยะเสียงต้องอยู่ระหว่าง {MIN_RANGE}-{TECH_MAX} บล็อก")
            return False
        if not self._unlimited(player) and value > self._voice_range_max:
            player.send_error_message(f"[VoiceCraft] ระยะสูงสุดที่แอดมินกำหนดคือ {self._voice_range_max} บล็อก")
            self._publish_tags(player, self._current_range(player))
            return False
        key = self._player_key(player)
        old = self._voice_ranges.get(key, self._voice_range_default)
        self._voice_ranges[key] = value
        self._save_ranges()
        self._publish_tags(player, value)
        state = self._states.get(key)
        if state is not None:
            self._bridge_send(self._state_message(state))
        if announce:
            player.send_message(f"§a[VoiceCraft Server] ตั้งระยะเสียงของคุณเป็น {value} บล็อกแล้ว§r")
        if old != value:
            self.logger.info(f"VOICE RANGE player={player.name} {old}->{value} operator={self._unlimited(player)}")
        return True

    def _publish_tags(self, player: Player, value: int) -> None:
        desired_value = f"{VALUE_PREFIX}{value}"
        desired_max = f"{MAX_PREFIX}{self._voice_range_max}"
        tags = set(player.scoreboard_tags)
        for tag in tuple(tags):
            if tag.startswith(VALUE_PREFIX) and tag != desired_value:
                player.remove_scoreboard_tag(tag)
                tags.discard(tag)
            elif tag.startswith(MAX_PREFIX) and tag != desired_max:
                player.remove_scoreboard_tag(tag)
                tags.discard(tag)
        if desired_value not in tags:
            player.add_scoreboard_tag(desired_value)
        if desired_max not in tags:
            player.add_scoreboard_tag(desired_max)

    def _sync_player(self, player: Player, emit: bool) -> None:
        value = self._current_range(player)
        self._voice_ranges.setdefault(self._player_key(player), value)
        self._publish_tags(player, value)
        if emit:
            state = self._states.get(self._player_key(player))
            if state is not None:
                self._bridge_send(self._state_message(state))

    def _open_vc_menu(self, player: Player) -> None:
        key = self._player_key(player)
        if key in self._pending_unbind_requests:
            binding = "Disconnecting"
        elif key in self._bound_players:
            binding = "Bound"
        elif key in self._pending_bind_keys:
            binding = "Pending"
        else:
            binding = "Not bound"
        current = self._current_range(player)
        limit = "Unlimited (Operator)" if self._unlimited(player) else f"{self._voice_range_max} blocks"
        form = ActionForm(
            title="VoiceCraft",
            content=(f"VoiceCraft Endstone v{self.version}\nBridge: {self._bridge_status_text()}\n"
                     f"Microphone: {binding}\nVoice Range: {current} blocks\nMaximum: {limit}\n\nเลือกเมนูที่ต้องการ"),
        )
        if key in self._bound_players:
            form.add_button("Disconnect / Unbind Microphone", on_click=self._menu_disconnect)
        elif key in self._pending_bind_keys:
            form.add_button("Cancel Pending Bind", on_click=self._menu_unbind)
        elif key not in self._pending_unbind_requests:
            form.add_button("Bind Microphone", on_click=self._menu_bind)
        form.add_button("Voice Range", on_click=self._menu_voice_range)
        form.add_button("Status", on_click=self._menu_status)
        if self._admin(player):
            form.add_button("Admin Settings", on_click=self._menu_range_admin)
        form.add_button("Tracked Players (Admin)", on_click=self._menu_dump)
        player.send_form(form)

    def _menu_voice_range(self, player: Player) -> None:
        current = self._current_range(player)
        limit = "ไม่จำกัดสำหรับ Operator" if self._unlimited(player) else f"1-{self._voice_range_max} บล็อก"
        form = ActionForm(title="VoiceCraft - Voice Range", content=f"ระยะปัจจุบัน: {current} บล็อก\nช่วงที่อนุญาต: {limit}")
        form.add_button("กำหนดเอง", on_click=self._menu_range_custom)
        form.add_button("5 บล็อก", on_click=lambda p: self._preset(p, 5))
        form.add_button("10 บล็อก", on_click=lambda p: self._preset(p, 10))
        form.add_button("20 บล็อก", on_click=lambda p: self._preset(p, 20))
        form.add_button("ย้อนกลับ", on_click=self._open_vc_menu)
        player.send_form(form)

    def _preset(self, player: Player, value: int) -> None:
        self._set_range(player, value, announce=True)
        self._menu_voice_range(player)

    def _menu_range_custom(self, player: Player) -> None:
        current = self._current_range(player)
        limit = "Operator: ไม่ติด Max" if self._unlimited(player) else f"1-{self._voice_range_max}"
        player.send_form(ModalForm(
            title="VoiceCraft - Custom Voice Range",
            controls=[TextInput(label=f"ระยะเสียง ({limit})\nค่าปัจจุบัน: {current}", placeholder=str(current))],
            submit_button="บันทึก",
            on_submit=self._submit_custom_range,
            on_close=self._menu_voice_range,
        ))

    def _submit_custom_range(self, player: Player, response: object) -> None:
        try:
            value = int(self._extract_binding_key(response).strip())
        except (TypeError, ValueError):
            player.send_error_message("[VoiceCraft] กรุณากรอกระยะเสียงเป็นจำนวนเต็ม")
            self._menu_voice_range(player)
            return
        self._set_range(player, value, announce=True)
        self._menu_voice_range(player)

    def _menu_range_admin(self, player: Player) -> None:
        if not self._admin(player):
            return
        form = ActionForm(
            title="VoiceCraft - Admin Settings",
            content=(f"Maximum Voice Range: {self._voice_range_max} blocks\n"
                     f"Default Voice Range: {self._voice_range_default} blocks\n\nOperator ไม่ติด Max"),
        )
        form.add_button("Set Maximum Voice Range", on_click=self._menu_admin_max)
        form.add_button("Back", on_click=self._open_vc_menu)
        player.send_form(form)

    def _menu_admin_max(self, player: Player) -> None:
        if not self._admin(player):
            return
        player.send_form(ModalForm(
            title="VoiceCraft - Maximum Voice Range",
            controls=[TextInput(label=f"ระยะสูงสุดผู้เล่นทั่วไป\nค่าปัจจุบัน: {self._voice_range_max}", placeholder=str(self._voice_range_max))],
            submit_button="บันทึก",
            on_submit=self._submit_admin_max,
            on_close=self._menu_range_admin,
        ))

    def _submit_admin_max(self, player: Player, response: object) -> None:
        if not self._admin(player):
            return
        try:
            value = int(self._extract_binding_key(response).strip())
        except (TypeError, ValueError):
            player.send_error_message("[VoiceCraft] กรุณากรอก Maximum Voice Range เป็นจำนวนเต็ม")
            self._menu_range_admin(player)
            return
        if not MIN_RANGE <= value <= TECH_MAX:
            player.send_error_message(f"[VoiceCraft] Maximum Voice Range ต้องอยู่ระหว่าง {MIN_RANGE}-{TECH_MAX}")
            self._menu_range_admin(player)
            return
        old = self._voice_range_max
        self._voice_range_max = value
        section = self.config.setdefault("voice_range", {})
        if not isinstance(section, dict):
            section = {}
            self.config["voice_range"] = section
        section["max_blocks"] = value
        self.save_config()
        for online in self.server.online_players:
            key = self._player_key(online)
            if not self._unlimited(online) and self._voice_ranges.get(key, self._voice_range_default) > value:
                self._voice_ranges[key] = value
                state = self._states.get(key)
                if state is not None:
                    self._bridge_send(self._state_message(state))
            self._publish_tags(online, self._current_range(online))
        self._save_ranges()
        player.send_message(f"§a[VoiceCraft Server] Maximum Voice Range เปลี่ยนจาก {old} เป็น {value} บล็อกแล้ว§r")
        self._menu_range_admin(player)
