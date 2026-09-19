#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import json
import sys
import tempfile
import zipfile

from PIL import Image

import build_item_mic_addon as base
import build_item_mic_v2_5_5_ddui_addon as ui_base
import build_item_mic_v2_6_9_ddui_bind_addon as previous

VERSION = [2, 6, 10]


def patch_manifest(text: str, name: str, description: str) -> str:
    data = json.loads(text)
    data["header"]["name"] = name
    data["header"]["description"] = description
    data["header"]["version"] = VERSION
    for module in data.get("modules", []):
        module["version"] = VERSION
    for dependency in data.get("dependencies", []):
        if dependency.get("uuid") == "cb345edb-6e6c-49ac-9950-e2ae07bda214":
            dependency["version"] = VERSION
        if dependency.get("module_name") == "@minecraft/server-ui":
            dependency["version"] = "2.1.0"
    return json.dumps(data, ensure_ascii=False, indent=2) + "\n"


def patch_script(js: str) -> str:
    js = previous.patch_script(js)

    settings_set_anchor = "const openSettingsPlayers = new Set();"
    settings_set_replacement = """const openSettingsPlayers = new Set();
const openSettingsForms = new Map();"""
    if settings_set_anchor not in js:
        raise RuntimeError("Item Mic 2.6.10 settings form map anchor missing")
    js = js.replace(settings_set_anchor, settings_set_replacement, 1)

    form_end_anchor = '''      .closeButton();

    refreshId = system.runInterval(() => {'''
    form_end_replacement = '''      .closeButton();

    openSettingsForms.set(player.id, form);

    refreshId = system.runInterval(() => {'''
    if form_end_anchor not in js:
        raise RuntimeError("Item Mic 2.6.10 settings form registration anchor missing")
    js = js.replace(form_end_anchor, form_end_replacement, 1)

    refresh_anchor = '''    refreshId = system.runInterval(() => {
      try {
        const refreshed = stateFor(player);'''
    refresh_replacement = '''    refreshId = system.runInterval(() => {
      try {
        const connectionState = bindState(player);
        if (connectionState !== "bound") {
          console.warn(
            "[VoiceCraftItem/BP] MIC_SETTINGS_CLOSE_BIND_STATE player=" +
            player.name + " state=" + connectionState
          );
          try {
            form.close();
          } catch {}
          return;
        }

        const refreshed = stateFor(player);'''
    if refresh_anchor not in js:
        raise RuntimeError("Item Mic 2.6.10 settings refresh anchor missing")
    js = js.replace(refresh_anchor, refresh_replacement, 1)

    finally_anchor = '''    openSettingsPlayers.delete(player.id);
  }
}

const BIND_DDUI_READY_TAG'''
    finally_replacement = '''    openSettingsForms.delete(player.id);
    openSettingsPlayers.delete(player.id);
  }
}

const BIND_DDUI_READY_TAG'''
    if finally_anchor not in js:
        raise RuntimeError("Item Mic 2.6.10 settings finally anchor missing")
    js = js.replace(finally_anchor, finally_replacement, 1)

    bind_helper_anchor = '''function openBindFromMic(player) {
  if (openBindPlayers.has(player.id)) return;
'''
    bind_helper_replacement = '''function closeMicSettingsForBind(player) {
  const settingsForm = openSettingsForms.get(player.id);
  if (!settingsForm) return;

  try {
    settingsForm.close();
  } catch (e) {
    console.warn(
      "[VoiceCraftItem/BP] Mic Settings close-before-Bind failed player=" +
      player.name + ": " + e
    );
  }
}

function openBindFromMic(player) {
  if (openBindPlayers.has(player.id)) return;
  closeMicSettingsForBind(player);
'''
    if bind_helper_anchor not in js:
        raise RuntimeError("Item Mic 2.6.10 openBindFromMic anchor missing")
    js = js.replace(bind_helper_anchor, bind_helper_replacement, 1)

    show_bind_anchor = '''async function showBindDdui(player, openToken) {
  if (openBindPlayers.has(player.id)) return;

  // Never take the Mic from a player that is already authoritatively bound.'''
    show_bind_replacement = '''async function showBindDdui(player, openToken) {
  if (openBindPlayers.has(player.id)) return;

  closeMicSettingsForBind(player);

  // Never take the Mic from a player that is already authoritatively bound.'''
    if show_bind_anchor not in js:
        raise RuntimeError("Item Mic 2.6.10 showBindDdui overlap anchor missing")
    js = js.replace(show_bind_anchor, show_bind_replacement, 1)

    leave_anchor = '''world.afterEvents.playerLeave.subscribe((ev) => {
  openBindPlayers.delete(ev.playerId);'''
    leave_replacement = '''world.afterEvents.playerLeave.subscribe((ev) => {
  openSettingsForms.delete(ev.playerId);
  openSettingsPlayers.delete(ev.playerId);
  openBindPlayers.delete(ev.playerId);'''
    if leave_anchor not in js:
        raise RuntimeError("Item Mic 2.6.10 playerLeave settings cleanup anchor missing")
    js = js.replace(leave_anchor, leave_replacement, 1)

    js = js.replace(
        "[VoiceCraftItem/BP] Loaded v2.6.9 — Mic withheld during Bind + authoritative Endstone state",
        "[VoiceCraftItem/BP] Loaded v2.6.10 — Settings disconnect close + stale-safe Bind lifecycle",
        1,
    )

    required = [
        "openSettingsForms",
        "MIC_SETTINGS_CLOSE_BIND_STATE",
        "closeMicSettingsForBind",
        "Mic Settings close-before-Bind failed",
        'connectionState !== "bound"',
        "openSettingsForms.set(player.id, form)",
        "openSettingsForms.delete(player.id)",
        "withholdMicForBind",
        "restoreMicAfterBind",
        "voicecraft.bind.check.",
        "voicecraft.bind.check_result.",
        "voicecraft.vr.ack.",
        "voicecraft.vr.sync.",
        "Loaded v2.6.10",
    ]
    missing = [value for value in required if value not in js]
    if missing:
        raise RuntimeError(f"Item Mic 2.6.10 settings/Bind lifecycle patch failed: {missing}")

    return js


def main() -> None:
    repo = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
    output = Path(
        sys.argv[2]
        if len(sys.argv) > 2
        else "release-assets/VoiceCraft_ItemMic_v2.6.10_DDUI-Bind.mcaddon"
    )
    if not output.is_absolute():
        output = repo / output

    logo = repo / "VoiceCraft.Guest.Patch/VoiceCraft.Server.Android/Resources/drawable/voicecraft_logo.webp"
    if not logo.exists():
        raise SystemExit(f"VoiceCraft logo not found: {logo}")

    files = dict(base.TEXT_FILES)
    files["BP/manifest.json"] = patch_manifest(
        files["BP/manifest.json"],
        "VoiceCraft Item Mic BP v2.6.10 DDUI Bind",
        "Auto-closes Mic Settings on disconnect, prevents Settings/Bind overlap, retains Bind Mic withholding and Voice Range ACK sync.",
    )
    files["RP/manifest.json"] = patch_manifest(
        files["RP/manifest.json"],
        "VoiceCraft Mic Icons RP v2.6.10",
        "Inventory icons plus invisible held Mic model for VoiceCraft Item Mic v2.6.10.",
    )

    for path in (
        "BP/items/mic_hold.item.json",
        "BP/items/mic_toggle.item.json",
        "BP/items/mic_off.item.json",
        "BP/items/mic_on.item.json",
    ):
        files[path] = ui_base.stable.hide_from_creative(files[path])

    files["BP/scripts/main.js"] = patch_script(files["BP/scripts/main.js"])

    files["RP/models/entity/voicecraft_mic_invisible.geo.json"] = ui_base.stable.INVISIBLE_GEOMETRY
    files["RP/render_controllers/voicecraft_mic_invisible.render_controllers.json"] = ui_base.stable.INVISIBLE_RENDER_CONTROLLER
    files["RP/attachables/mic_off.entity.json"] = ui_base.stable.attachable("voicecraft:mic_off")
    files["RP/attachables/mic_on.entity.json"] = ui_base.stable.attachable("voicecraft:mic_on")
    files["RP/attachables/mic_hold.entity.json"] = ui_base.stable.attachable("voicecraft:mic_hold")
    files["RP/attachables/mic_toggle.entity.json"] = ui_base.stable.attachable("voicecraft:mic_toggle")

    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="voicecraft-itemmic-2.6.10-ddui-bind-") as td:
        tmp = Path(td)
        bp = tmp / "BP"
        rp = tmp / "RP"

        for rel, file_content in files.items():
            path = tmp / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(file_content, encoding="utf-8")

        items = rp / "textures/items"
        items.mkdir(parents=True, exist_ok=True)
        (items / "icon_mic_off.png").write_bytes(
            __import__("base64").b64decode(base.ICON_OFF_B64)
        )
        (items / "icon_mic_on.png").write_bytes(
            __import__("base64").b64decode(base.ICON_ON_B64)
        )

        entity_textures = rp / "textures/entity"
        entity_textures.mkdir(parents=True, exist_ok=True)
        Image.new("RGBA", (1, 1), (0, 0, 0, 0)).save(
            entity_textures / "voicecraft_mic_invisible.png", "PNG"
        )

        with Image.open(logo) as image:
            rgba = image.convert("RGBA")
            rgba.save(bp / "pack_icon.png", "PNG")
            rgba.save(rp / "pack_icon.png", "PNG")

        rp_pack = tmp / "VoiceCraft_ItemMic_RP_v2.6.10.mcpack"
        bp_pack = tmp / "VoiceCraft_ItemMic_BP_v2.6.10.mcpack"
        base.zip_dir(rp, rp_pack)
        base.zip_dir(bp, bp_pack)

        with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.write(rp_pack, rp_pack.name)
            zf.write(bp_pack, bp_pack.name)

    print(output)


if __name__ == "__main__":
    main()
