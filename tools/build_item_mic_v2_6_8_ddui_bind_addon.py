#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import json
import sys
import tempfile
import zipfile

from PIL import Image

import build_item_mic_addon as base
import build_item_mic_v2_6_7_ddui_bind_addon as previous

VERSION = [2, 6, 8]


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

    constant_anchor = 'const BIND_UI_REQUEST_PREFIX = "voicecraft.bind.ui.request.";\n'
    if constant_anchor not in js:
        raise RuntimeError("Item Mic 2.6.8 bind check constant anchor missing")
    js = js.replace(
        constant_anchor,
        constant_anchor
        + 'const BIND_CHECK_PREFIX = "voicecraft.bind.check.";\n'
        + 'const BIND_CHECK_RESULT_PREFIX = "voicecraft.bind.check_result.";\n',
        1,
    )

    old_guard = "const bindStateCheckPlayers = new Set();"
    new_guard = """const bindCheckPendingByPlayer = new Map();
let bindCheckSequence = 0;"""
    if old_guard not in js:
        raise RuntimeError("Item Mic 2.6.8 old recheck guard missing")
    js = js.replace(old_guard, new_guard, 1)

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

    new_use = '''function nextBindCheckId() {
  bindCheckSequence = (bindCheckSequence + 1) % 1000000;
  return "m" + String(system.currentTick) + "_" + String(bindCheckSequence);
}

function clearBindCheckTags(player) {
  removeTagsByPrefix(player, BIND_CHECK_PREFIX);
  removeTagsByPrefix(player, BIND_CHECK_RESULT_PREFIX);
}

function consumeBindCheckResult(player, requestId) {
  if (!requestId) return "";
  const prefix = BIND_CHECK_RESULT_PREFIX + requestId + ".";
  try {
    for (const tag of player.getTags()) {
      if (!tag.startsWith(prefix)) continue;
      const state = tag.slice(prefix.length);
      try {
        player.removeTag(tag);
      } catch {}
      return state;
    }
  } catch {}
  return "";
}

function routeMicByAuthoritativeState(player, state) {
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

  if (
    state === "unbound" ||
    state === "error" ||
    state === "reconnecting" ||
    state === "rebind_required"
  ) {
    openBindFromMic(player);
    return;
  }

  player.sendMessage("§c[VoiceCraft] ไม่สามารถตรวจสอบสถานะการเชื่อมต่อได้ กรุณาลองใหม่§r");
}

function pollMicBindCheck(player, requestId, attemptsLeft) {
  if (bindCheckPendingByPlayer.get(player.id) !== requestId) return;

  const state = consumeBindCheckResult(player, requestId);
  if (state) {
    bindCheckPendingByPlayer.delete(player.id);
    routeMicByAuthoritativeState(player, state);
    return;
  }

  if (attemptsLeft <= 0) {
    bindCheckPendingByPlayer.delete(player.id);
    clearBindCheckTags(player);
    player.sendMessage("§c[VoiceCraft] ไม่สามารถตรวจสอบสถานะการเชื่อมต่อได้ กรุณาลองใหม่§r");
    return;
  }

  system.runTimeout(
    () => pollMicBindCheck(player, requestId, attemptsLeft - 1),
    2
  );
}

function handleMicUse(player) {
  if (bindCheckPendingByPlayer.has(player.id)) return;

  const requestId = nextBindCheckId();
  clearBindCheckTags(player);

  try {
    player.addTag(BIND_CHECK_PREFIX + requestId);
  } catch (e) {
    console.warn(
      "[VoiceCraftItem/BP] bind state check request failed player=" +
      player.name + ": " + e
    );
    player.sendMessage("§c[VoiceCraft] ไม่สามารถตรวจสอบสถานะการเชื่อมต่อได้ กรุณาลองใหม่§r");
    return;
  }

  bindCheckPendingByPlayer.set(player.id, requestId);
  system.runTimeout(
    () => pollMicBindCheck(player, requestId, 20),
    2
  );
}'''
    if old_use not in js:
        raise RuntimeError("Item Mic 2.6.8 handleMicUse anchor missing")
    js = js.replace(old_use, new_use, 1)

    js = js.replace(
        "bindStateCheckPlayers.delete(player.id);",
        "bindCheckPendingByPlayer.delete(player.id);\n      clearBindCheckTags(player);",
        1,
    )
    js = js.replace(
        "bindStateCheckPlayers.delete(ev.playerId);",
        "bindCheckPendingByPlayer.delete(ev.playerId);",
        1,
    )

    js = js.replace(
        "[VoiceCraftItem/BP] Loaded v2.6.7 — authoritative Bind state + Voice Range ACK sync",
        "[VoiceCraftItem/BP] Loaded v2.6.8 — Endstone Bind check handshake + Voice Range ACK sync",
        1,
    )

    required = [
        "voicecraft.bind.check.",
        "voicecraft.bind.check_result.",
        "bindCheckPendingByPlayer",
        "nextBindCheckId",
        "consumeBindCheckResult",
        "routeMicByAuthoritativeState",
        "pollMicBindCheck",
        "player.addTag(BIND_CHECK_PREFIX + requestId)",
        'state === "bound"',
        "showSettings(player);",
        'state === "reconnecting"',
        'state === "rebind_required"',
        "openBindFromMic(player);",
        "ไม่สามารถตรวจสอบสถานะการเชื่อมต่อได้ กรุณาลองใหม่",
        "Loaded v2.6.8",
        "voicecraft.vr.ack.",
        "voicecraft.vr.sync.",
        "submittedCloseRequested",
    ]
    missing = [value for value in required if value not in js]
    if missing:
        raise RuntimeError(f"Item Mic 2.6.8 Bind handshake patch failed: {missing}")

    forbidden = [
        "bindStateCheckPlayers",
        'const state = bindState(player);\n\n  if (state === "bound")',
        "const refreshedState = bindState(player);",
    ]
    leftovers = [value for value in forbidden if value in js]
    if leftovers:
        raise RuntimeError(f"Legacy local Bind decision survived in 2.6.8: {leftovers}")

    return js


def main() -> None:
    repo = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
    output = Path(
        sys.argv[2]
        if len(sys.argv) > 2
        else "release-assets/VoiceCraft_ItemMic_v2.6.8_DDUI-Bind.mcaddon"
    )
    if not output.is_absolute():
        output = repo / output

    logo = repo / "VoiceCraft.Guest.Patch/VoiceCraft.Server.Android/Resources/drawable/voicecraft_logo.webp"
    if not logo.exists():
        raise SystemExit(f"VoiceCraft logo not found: {logo}")

    files = dict(base.TEXT_FILES)
    files["BP/manifest.json"] = patch_manifest(
        files["BP/manifest.json"],
        "VoiceCraft Item Mic BP v2.6.8 DDUI Bind",
        "Endstone-authoritative Mic Bind-state handshake plus Voice Range ACK synchronization.",
    )
    files["RP/manifest.json"] = patch_manifest(
        files["RP/manifest.json"],
        "VoiceCraft Mic Icons RP v2.6.8",
        "Inventory icons plus invisible held Mic model for VoiceCraft Item Mic v2.6.8.",
    )

    for path in (
        "BP/items/mic_hold.item.json",
        "BP/items/mic_toggle.item.json",
        "BP/items/mic_off.item.json",
        "BP/items/mic_on.item.json",
    ):
        files[path] = previous.previous.ui_base.stable.hide_from_creative(files[path])

    files["BP/scripts/main.js"] = patch_script(files["BP/scripts/main.js"])

    files["RP/models/entity/voicecraft_mic_invisible.geo.json"] = previous.previous.ui_base.stable.INVISIBLE_GEOMETRY
    files["RP/render_controllers/voicecraft_mic_invisible.render_controllers.json"] = previous.previous.ui_base.stable.INVISIBLE_RENDER_CONTROLLER
    files["RP/attachables/mic_off.entity.json"] = previous.previous.ui_base.stable.attachable("voicecraft:mic_off")
    files["RP/attachables/mic_on.entity.json"] = previous.previous.ui_base.stable.attachable("voicecraft:mic_on")
    files["RP/attachables/mic_hold.entity.json"] = previous.previous.ui_base.stable.attachable("voicecraft:mic_hold")
    files["RP/attachables/mic_toggle.entity.json"] = previous.previous.ui_base.stable.attachable("voicecraft:mic_toggle")

    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="voicecraft-itemmic-2.6.8-ddui-bind-") as td:
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

        rp_pack = tmp / "VoiceCraft_ItemMic_RP_v2.6.8.mcpack"
        bp_pack = tmp / "VoiceCraft_ItemMic_BP_v2.6.8.mcpack"
        base.zip_dir(rp, rp_pack)
        base.zip_dir(bp, bp_pack)

        with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.write(rp_pack, rp_pack.name)
            zf.write(bp_pack, bp_pack.name)

    print(output)


if __name__ == "__main__":
    main()
