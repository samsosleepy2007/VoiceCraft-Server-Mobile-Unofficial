#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import json
import sys
import tempfile
import zipfile

from PIL import Image

import build_item_mic_addon as base
import build_item_mic_v2_6_6_ddui_bind_addon as previous

VERSION = [2, 6, 7]


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

    old_sets = '''const openBindPlayers = new Set();
const bindLastOpenToken = new Map();
const bindRetryAfterTick = new Map();'''
    new_sets = '''const openBindPlayers = new Set();
const bindLastOpenToken = new Map();
const bindRetryAfterTick = new Map();
const bindStateCheckPlayers = new Set();'''
    if old_sets not in js:
        raise RuntimeError("Item Mic 2.6.7 Bind state set anchor missing")
    js = js.replace(old_sets, new_sets, 1)

    old_state = '''function bindState(player) {
  return getTagValue(player, BIND_STATE_PREFIX) || "unbound";
}'''
    new_state = '''function bindState(player) {
  const state = getTagValue(player, BIND_STATE_PREFIX) || "unbound";
  if (
    state === "unbound" ||
    state === "pending" ||
    state === "bound" ||
    state === "reconnecting" ||
    state === "rebind_required" ||
    state === "error" ||
    state === "disconnecting"
  ) {
    return state;
  }
  return "unbound";
}'''
    if old_state not in js:
        raise RuntimeError("Item Mic 2.6.7 bindState anchor missing")
    js = js.replace(old_state, new_state, 1)

    old_use = '''function handleMicUse(player) {
  const state = bindState(player);

  if (state === "bound") {
    showSettings(player);
    return;
  }

  if (state === "pending") {
    player.sendMessage("§e[VoiceCraft] กำลังตรวจสอบ Binding Key กรุณารอสักครู่...§r");
    return;
  }

  if (state === "disconnecting") {
    player.sendMessage("§e[VoiceCraft] กำลังยกเลิกการเชื่อมต่อ กรุณารอสักครู่...§r");
    return;
  }

  // unbound / error / rebind_required / reconnecting all allow the player to
  // explicitly reopen Bind immediately by using any Mic item.
  openBindFromMic(player);
}'''
    new_use = '''function handleMicUse(player) {
  const state = bindState(player);

  if (state === "bound") {
    showSettings(player);
    return;
  }

  if (state === "pending") {
    player.sendMessage("§e[VoiceCraft] กำลังตรวจสอบ Binding Key กรุณารอสักครู่...§r");
    return;
  }

  if (state === "disconnecting") {
    player.sendMessage("§e[VoiceCraft] กำลังยกเลิกการเชื่อมต่อ กรุณารอสักครู่...§r");
    return;
  }

  // A successful Bind result and its authoritative state tag can arrive a
  // fraction of a second after the submit DDUI closes. Before treating a
  // stale unbound/error tag as real, allow Endstone one reconciliation cycle.
  if (state === "unbound" || state === "error") {
    if (bindStateCheckPlayers.has(player.id)) return;
    bindStateCheckPlayers.add(player.id);

    system.runTimeout(() => {
      bindStateCheckPlayers.delete(player.id);
      const refreshedState = bindState(player);

      if (refreshedState === "bound") {
        showSettings(player);
        return;
      }
      if (refreshedState === "pending") {
        player.sendMessage("§e[VoiceCraft] กำลังตรวจสอบ Binding Key กรุณารอสักครู่...§r");
        return;
      }
      if (refreshedState === "disconnecting") {
        player.sendMessage("§e[VoiceCraft] กำลังยกเลิกการเชื่อมต่อ กรุณารอสักครู่...§r");
        return;
      }

      openBindFromMic(player);
    }, 4);
    return;
  }

  // rebind_required / reconnecting remain explicit recovery paths.
  openBindFromMic(player);
}'''
    if old_use not in js:
        raise RuntimeError("Item Mic 2.6.7 handleMicUse anchor missing")
    js = js.replace(old_use, new_use, 1)

    old_spawn = '''      openBindPlayers.delete(player.id);
      bindLastOpenToken.delete(player.id);
      bindRetryAfterTick.delete(player.id);
      removeTagsByPrefix(player, BIND_UI_CLOSED_PREFIX);'''
    new_spawn = '''      openBindPlayers.delete(player.id);
      bindLastOpenToken.delete(player.id);
      bindRetryAfterTick.delete(player.id);
      bindStateCheckPlayers.delete(player.id);
      removeTagsByPrefix(player, BIND_UI_CLOSED_PREFIX);'''
    if old_spawn not in js:
        raise RuntimeError("Item Mic 2.6.7 initial spawn cleanup anchor missing")
    js = js.replace(old_spawn, new_spawn, 1)

    old_leave = '''world.afterEvents.playerLeave.subscribe((ev) => {
  openBindPlayers.delete(ev.playerId);
  bindLastOpenToken.delete(ev.playerId);
  bindRetryAfterTick.delete(ev.playerId);
});'''
    new_leave = '''world.afterEvents.playerLeave.subscribe((ev) => {
  openBindPlayers.delete(ev.playerId);
  bindLastOpenToken.delete(ev.playerId);
  bindRetryAfterTick.delete(ev.playerId);
  bindStateCheckPlayers.delete(ev.playerId);
});'''
    if old_leave not in js:
        raise RuntimeError("Item Mic 2.6.7 playerLeave cleanup anchor missing")
    js = js.replace(old_leave, new_leave, 1)

    js = js.replace(
        "[VoiceCraftItem/BP] Loaded v2.6.6 — authoritative Voice Range ACK sync + stable Bind",
        "[VoiceCraftItem/BP] Loaded v2.6.7 — authoritative Bind state + Voice Range ACK sync",
        1,
    )

    required = [
        "bindStateCheckPlayers",
        'state === "bound"',
        'state === "reconnecting"',
        'state === "rebind_required"',
        'state === "disconnecting"',
        'if (state === "unbound" || state === "error")',
        "system.runTimeout(() =>",
        "const refreshedState = bindState(player);",
        'if (refreshedState === "bound")',
        "showSettings(player);",
        "openBindFromMic(player);",
        "}, 4);",
        "Loaded v2.6.7",
        "voicecraft.vr.ack.",
        "voicecraft.vr.sync.",
        "submittedCloseRequested",
    ]
    missing = [value for value in required if value not in js]
    if missing:
        raise RuntimeError(f"Item Mic 2.6.7 Bind-state patch failed: {missing}")

    return js


def main() -> None:
    repo = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
    output = Path(
        sys.argv[2]
        if len(sys.argv) > 2
        else "release-assets/VoiceCraft_ItemMic_v2.6.7_DDUI-Bind.mcaddon"
    )
    if not output.is_absolute():
        output = repo / output

    logo = repo / "VoiceCraft.Guest.Patch/VoiceCraft.Server.Android/Resources/drawable/voicecraft_logo.webp"
    if not logo.exists():
        raise SystemExit(f"VoiceCraft logo not found: {logo}")

    files = dict(base.TEXT_FILES)
    files["BP/manifest.json"] = patch_manifest(
        files["BP/manifest.json"],
        "VoiceCraft Item Mic BP v2.6.7 DDUI Bind",
        "Authoritative Bind-state checks plus Voice Range ACK synchronization and stable DDUI.",
    )
    files["RP/manifest.json"] = patch_manifest(
        files["RP/manifest.json"],
        "VoiceCraft Mic Icons RP v2.6.7",
        "Inventory icons plus invisible held Mic model for VoiceCraft Item Mic v2.6.7.",
    )

    for path in (
        "BP/items/mic_hold.item.json",
        "BP/items/mic_toggle.item.json",
        "BP/items/mic_off.item.json",
        "BP/items/mic_on.item.json",
    ):
        files[path] = previous.ui_base.stable.hide_from_creative(files[path])

    files["BP/scripts/main.js"] = patch_script(files["BP/scripts/main.js"])

    files["RP/models/entity/voicecraft_mic_invisible.geo.json"] = previous.ui_base.stable.INVISIBLE_GEOMETRY
    files["RP/render_controllers/voicecraft_mic_invisible.render_controllers.json"] = previous.ui_base.stable.INVISIBLE_RENDER_CONTROLLER
    files["RP/attachables/mic_off.entity.json"] = previous.ui_base.stable.attachable("voicecraft:mic_off")
    files["RP/attachables/mic_on.entity.json"] = previous.ui_base.stable.attachable("voicecraft:mic_on")
    files["RP/attachables/mic_hold.entity.json"] = previous.ui_base.stable.attachable("voicecraft:mic_hold")
    files["RP/attachables/mic_toggle.entity.json"] = previous.ui_base.stable.attachable("voicecraft:mic_toggle")

    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="voicecraft-itemmic-2.6.7-ddui-bind-") as td:
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

        rp_pack = tmp / "VoiceCraft_ItemMic_RP_v2.6.7.mcpack"
        bp_pack = tmp / "VoiceCraft_ItemMic_BP_v2.6.7.mcpack"
        base.zip_dir(rp, rp_pack)
        base.zip_dir(bp, bp_pack)

        with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.write(rp_pack, rp_pack.name)
            zf.write(bp_pack, bp_pack.name)

    print(output)


if __name__ == "__main__":
    main()
