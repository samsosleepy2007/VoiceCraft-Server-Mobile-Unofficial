#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import base64
import json
import sys
import tempfile
import zipfile

import build_item_mic_addon as base

VERSION = [2, 3, 0]
VALUE_PREFIX = "voicecraft.vr.value."
REQUEST_PREFIX = "voicecraft.vr.request."
MAX_PREFIX = "voicecraft.vr.max."


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
    return json.dumps(data, ensure_ascii=False, indent=2) + "\n"


def patch_script(js: str) -> str:
    js = js.replace(
        '  EquipmentSlot,\n} from "@minecraft/server";',
        '  EquipmentSlot,\n  PlayerPermissionLevel,\n} from "@minecraft/server";',
        1,
    )
    js = js.replace(
        'import { ActionFormData } from "@minecraft/server-ui";',
        'import { ActionFormData, ModalFormData } from "@minecraft/server-ui";',
        1,
    )
    js = js.replace(
        'const PROP_LATCH = "voicecraft:toggle_latched";\nconst states = new Map();',
        'const PROP_LATCH = "voicecraft:toggle_latched";\n'
        'const PROP_VOICE_RANGE = "voicecraft:voice_range";\n'
        f'const RANGE_VALUE_PREFIX = "{VALUE_PREFIX}";\n'
        f'const RANGE_REQUEST_PREFIX = "{REQUEST_PREFIX}";\n'
        f'const RANGE_MAX_PREFIX = "{MAX_PREFIX}";\n'
        'const DEFAULT_VOICE_RANGE = 20;\nconst DEFAULT_MAX_RANGE = 150;\nconst states = new Map();',
        1,
    )

    marker = 'async function showSettings(player) {'
    start = js.index(marker)
    end = js.index('\nsystem.beforeEvents.startup.subscribe', start)
    replacement = r'''function isOperator(player) {
  try {
    return player.playerPermissionLevel === PlayerPermissionLevel.Operator;
  } catch {
    return false;
  }
}

function readTaggedNumber(player, prefix, fallback) {
  try {
    for (const tag of player.getTags()) {
      if (!tag.startsWith(prefix)) continue;
      const value = Number.parseInt(tag.substring(prefix.length), 10);
      if (Number.isFinite(value) && value >= 1) return value;
    }
  } catch {}
  return fallback;
}

function currentVoiceRange(player) {
  const serverValue = readTaggedNumber(player, RANGE_VALUE_PREFIX, 0);
  if (serverValue >= 1) {
    player.setDynamicProperty(PROP_VOICE_RANGE, serverValue);
    return serverValue;
  }
  const stored = Number(player.getDynamicProperty(PROP_VOICE_RANGE));
  return Number.isFinite(stored) && stored >= 1 ? Math.floor(stored) : DEFAULT_VOICE_RANGE;
}

function currentMaxRange(player) {
  return readTaggedNumber(player, RANGE_MAX_PREFIX, DEFAULT_MAX_RANGE);
}

function clearRequestTags(player) {
  try {
    for (const tag of player.getTags()) {
      if (tag.startsWith(RANGE_REQUEST_PREFIX)) player.removeTag(tag);
    }
  } catch {}
}

function syncVoiceRangeFromServer(player) {
  const serverValue = readTaggedNumber(player, RANGE_VALUE_PREFIX, 0);
  if (serverValue >= 1) player.setDynamicProperty(PROP_VOICE_RANGE, serverValue);
}

function requestVoiceRange(player, value) {
  value = Math.floor(Number(value));
  if (!Number.isFinite(value) || value < 1 || value > 30000000) {
    player.sendMessage("§c[VoiceCraft] ระยะเสียงต้องเป็นจำนวนเต็มตั้งแต่ 1 ขึ้นไป§r");
    return false;
  }
  const maximum = currentMaxRange(player);
  if (!isOperator(player) && value > maximum) {
    player.sendMessage(`§c[VoiceCraft] ระยะสูงสุดที่แอดมินกำหนดคือ ${maximum} บล็อก§r`);
    return false;
  }
  clearRequestTags(player);
  player.setDynamicProperty(PROP_VOICE_RANGE, value);
  player.addTag(`${RANGE_REQUEST_PREFIX}${value}`);
  return true;
}

async function showVoiceRangeCustom(player) {
  const current = currentVoiceRange(player);
  const maximum = currentMaxRange(player);
  const limit = isOperator(player) ? "Operator: ไม่จำกัดโดย Max ของเซิร์ฟเวอร์" : `กรอก 1-${maximum} บล็อก`;
  const form = new ModalFormData()
    .title("VoiceCraft • Custom Voice Range")
    .textField(`${limit}\nค่าปัจจุบัน: ${current}`, `เช่น ${current}`)
    .submitButton("บันทึก");
  let response;
  try {
    response = await form.show(player);
  } catch (e) {
    console.warn(`[VoiceCraftItem/BP] range form failed player=${player.name}: ${e}`);
    return;
  }
  if (response.canceled) return;
  const raw = response.formValues?.[0];
  const value = Number.parseInt(String(raw ?? ""), 10);
  if (requestVoiceRange(player, value)) {
    player.sendMessage(`§e[VoiceCraft] ส่งคำขอตั้งระยะเสียง ${value} บล็อกไปยังเซิร์ฟเวอร์แล้ว§r`);
  }
}

async function showVoiceRange(player) {
  syncVoiceRangeFromServer(player);
  const current = currentVoiceRange(player);
  const maximum = currentMaxRange(player);
  const limit = isOperator(player) ? "Unlimited (Operator)" : `${maximum} blocks`;
  const form = new ActionFormData()
    .title("VoiceCraft • Voice Range")
    .body(`ระยะเสียงปัจจุบัน: §e${current} บล็อก§r\nระยะสูงสุด: §b${limit}§r\n\nค่านี้กำหนดว่าเสียงของคุณจะไปถึงผู้เล่นอื่นได้ไกลเท่าไร`)
    .button("กำหนดเอง")
    .button("5 บล็อก")
    .button("10 บล็อก")
    .button("20 บล็อก")
    .button("ย้อนกลับ");
  let response;
  try {
    response = await form.show(player);
  } catch (e) {
    console.warn(`[VoiceCraftItem/BP] range menu failed player=${player.name}: ${e}`);
    return;
  }
  if (response.canceled || response.selection === undefined) return;
  if (response.selection === 0) return showVoiceRangeCustom(player);
  if (response.selection === 1) requestVoiceRange(player, 5);
  else if (response.selection === 2) requestVoiceRange(player, 10);
  else if (response.selection === 3) requestVoiceRange(player, 20);
  else return showSettings(player);
}

async function showSettings(player) {
  ensureMic(player);
  evaluate(player);
  syncVoiceRangeFromServer(player);
  const s = stateFor(player);
  const offMic = isMicId(getOffId(player));
  const voiceRange = currentVoiceRange(player);
  const form = new ActionFormData()
    .title("VoiceCraft • Mic Settings")
    .body(
      `สถานะไมค์: ${s.effective ? "§aON" : "§cOFF"}§r\n` +
      `ไอเทม: ${s.effective ? "§aMic On" : "§cMic Off"}§r\n` +
      `โหมดปัจจุบัน: §e${modeLabel(s.mode)}§r\n` +
      `ระยะเสียง: §b${voiceRange} บล็อก§r\n` +
      `มือซ้าย: ${offMic ? "§aMic อยู่มือซ้าย — บังคับ ON" : "ไม่มี Mic"}§r\n\n` +
      "เลือกโหมดหรือการตั้งค่าไมค์"
    )
    .button(`${s.mode === MODE_HOLD ? "✓ " : ""}Hold-to-Talk`)
    .button(`${s.mode === MODE_TOGGLE ? "✓ " : ""}Toggle`)
    .button("ตั้งค่าระยะเสียง")
    .button("ปิด");

  let response;
  try {
    response = await form.show(player);
  } catch (e) {
    console.warn(`[VoiceCraftItem/BP] form failed player=${player.name}: ${e}`);
    return;
  }
  if (response.canceled || response.selection === undefined || response.selection === 3) return;
  if (response.selection === 2) return showVoiceRange(player);

  const newMode = response.selection === 1 ? MODE_TOGGLE : MODE_HOLD;
  setMode(player, newMode);
  if (newMode === MODE_TOGGLE) {
    const mainMic = isMicId(getMainId(player));
    const offMicNow = isMicId(getOffId(player));
    setLatch(player, !!(mainMic && !offMicNow));
  } else {
    setLatch(player, false);
  }
  player.sendMessage(`§b[VoiceCraft] โหมดไมค์: §f${modeLabel(newMode)}`);
  states.delete(player.id);
  system.run(() => {
    evaluate(player);
    reassertMicFlags(player);
  });
}
'''
    js = js[:start] + replacement + js[end:]

    js = js.replace(
        '    evaluate(player);\n    console.warn(`[VoiceCraftItem/BP] READY player=${player.name} mode=${getMode(player)}`);',
        '    evaluate(player);\n    syncVoiceRangeFromServer(player);\n'
        '    console.warn(`[VoiceCraftItem/BP] READY player=${player.name} mode=${getMode(player)} range=${currentVoiceRange(player)}`);',
        1,
    )
    js = js.replace(
        '    ensureMic(player);\n    reassertMicFlags(player);',
        '    ensureMic(player);\n    reassertMicFlags(player);\n    syncVoiceRangeFromServer(player);',
        1,
    )
    js = js.replace(
        '[VoiceCraftItem/BP] Loaded v2.2.0 — Mic On/Off item variants; no JSON UI',
        '[VoiceCraftItem/BP] Loaded v2.3.0 — Mic modes + server-authoritative Voice Range',
        1,
    )

    required = [
        "PlayerPermissionLevel.Operator",
        "ModalFormData",
        "voicecraft.vr.request.",
        "ตั้งค่าระยะเสียง",
        "showVoiceRangeCustom",
        "currentMaxRange",
    ]
    missing = [value for value in required if value not in js]
    if missing:
        raise RuntimeError(f"Item Mic voice range patch failed: {missing}")
    return js


def main() -> None:
    repo = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
    output = Path(sys.argv[2] if len(sys.argv) > 2 else "release-assets/VoiceCraft_ItemMic_v2.3.0.mcaddon")
    if not output.is_absolute():
        output = repo / output
    logo = repo / "VoiceCraft.Guest.Patch/VoiceCraft.Server.Android/Resources/drawable/voicecraft_logo.webp"
    if not logo.exists():
        raise SystemExit(f"VoiceCraft logo not found: {logo}")

    files = dict(base.TEXT_FILES)
    files["BP/manifest.json"] = patch_manifest(
        files["BP/manifest.json"],
        "VoiceCraft Item Mic BP v2.3",
        "Mic modes, offhand always-on, Voice Range UI and VoiceCraft Server bridge.",
    )
    files["RP/manifest.json"] = patch_manifest(
        files["RP/manifest.json"],
        "VoiceCraft Mic Icons RP v2.3",
        "Item textures for VoiceCraft Mic v2.3.",
    )
    files["BP/scripts/main.js"] = patch_script(files["BP/scripts/main.js"])

    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="voicecraft-itemmic-2.3-") as td:
        tmp = Path(td)
        bp = tmp / "BP"
        rp = tmp / "RP"
        for rel, content in files.items():
            path = tmp / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
        items = rp / "textures/items"
        items.mkdir(parents=True, exist_ok=True)
        (items / "icon_mic_off.png").write_bytes(base64.b64decode(base.ICON_OFF_B64))
        (items / "icon_mic_on.png").write_bytes(base64.b64decode(base.ICON_ON_B64))
        with base.Image.open(logo) as image:
            rgba = image.convert("RGBA")
            rgba.save(bp / "pack_icon.png", "PNG")
            rgba.save(rp / "pack_icon.png", "PNG")
        rp_pack = tmp / "VoiceCraft_ItemMic_RP_v2.3.0.mcpack"
        bp_pack = tmp / "VoiceCraft_ItemMic_BP_v2.3.0.mcpack"
        base.zip_dir(rp, rp_pack)
        base.zip_dir(bp, bp_pack)
        with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.write(rp_pack, rp_pack.name)
            zf.write(bp_pack, bp_pack.name)
    print(output)


if __name__ == "__main__":
    main()
