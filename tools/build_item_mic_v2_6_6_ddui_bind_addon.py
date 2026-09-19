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
import build_item_mic_v2_6_5_ddui_bind_addon as previous

VERSION = [2, 6, 6]


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

    constants_anchor = 'const RANGE_MAX_PREFIX = "voicecraft.vr.max.";\n'
    if constants_anchor not in js:
        raise RuntimeError("Item Mic 2.6.6 Voice Range constant anchor missing")
    js = js.replace(
        constants_anchor,
        constants_anchor
        + 'const RANGE_ACK_PREFIX = "voicecraft.vr.ack.";\n'
        + 'const RANGE_SYNC_PREFIX = "voicecraft.vr.sync.";\n'
        + 'let rangeRequestSequence = 0;\n',
        1,
    )

    old_request = r'''function requestVoiceRange(player, value) {
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
'''

    new_request = r'''function clearRangeTagsByPrefix(player, prefix) {
  try {
    for (const tag of player.getTags()) {
      if (tag.startsWith(prefix)) {
        try {
          player.removeTag(tag);
        } catch {}
      }
    }
  } catch {}
}

function nextRangeRequestId() {
  rangeRequestSequence = (rangeRequestSequence + 1) % 1000000;
  return "r" + String(system.currentTick) + "_" + String(rangeRequestSequence);
}

function consumeVoiceRangeAck(player, requestId) {
  if (!requestId) return undefined;
  const prefix = RANGE_ACK_PREFIX + requestId + ".";
  try {
    for (const tag of player.getTags()) {
      if (!tag.startsWith(prefix)) continue;

      const payload = tag.slice(prefix.length);
      const separator = payload.indexOf(".");
      const status = separator >= 0 ? payload.slice(0, separator) : "";
      const rawValue = separator >= 0 ? payload.slice(separator + 1) : "";
      const value = Number.parseInt(rawValue, 10);

      try {
        player.removeTag(tag);
      } catch {}

      if (!Number.isFinite(value) || value < 1) {
        return { status: "error", value: 0 };
      }
      return { status, value };
    }
  } catch {}
  return undefined;
}

function requestVoiceRangeSync(player) {
  const requestId = nextRangeRequestId();
  clearRangeTagsByPrefix(player, RANGE_ACK_PREFIX);
  clearRangeTagsByPrefix(player, RANGE_SYNC_PREFIX);
  try {
    player.addTag(RANGE_SYNC_PREFIX + requestId);
    return requestId;
  } catch (e) {
    console.warn(
      "[VoiceCraftItem/BP] voice range sync request failed player=" +
      player.name + ": " + e
    );
    return "";
  }
}

function requestVoiceRange(player, value) {
  value = Math.floor(Number(value));
  if (!Number.isFinite(value) || value < 1 || value > 30000000) {
    player.sendMessage("§c[VoiceCraft] ระยะเสียงต้องเป็นจำนวนเต็มตั้งแต่ 1 ขึ้นไป§r");
    return "";
  }

  const maximum = currentMaxRange(player);
  if (!isOperator(player) && value > maximum) {
    player.sendMessage(`§c[VoiceCraft] ระยะสูงสุดที่แอดมินกำหนดคือ ${maximum} บล็อก§r`);
    return "";
  }

  const requestId = nextRangeRequestId();
  clearRequestTags(player);
  clearRangeTagsByPrefix(player, RANGE_ACK_PREFIX);
  clearRangeTagsByPrefix(player, RANGE_SYNC_PREFIX);

  try {
    player.addTag(`${RANGE_REQUEST_PREFIX}${requestId}.${value}`);
    return requestId;
  } catch (e) {
    console.warn(
      "[VoiceCraftItem/BP] voice range request failed player=" +
      player.name + ": " + e
    );
    return "";
  }
}
'''
    if old_request not in js:
        raise RuntimeError("Item Mic 2.6.6 requestVoiceRange anchor missing")
    js = js.replace(old_request, new_request, 1)

    state_anchor = '''    let pendingRange = null;
    let pendingChecks = 0;
'''
    state_replacement = '''    let confirmedRange = initialRange;
    let pendingRange = null;
    let pendingRequestId = "";
    let pendingChecks = 0;
    let syncRequestId = requestVoiceRangeSync(player);
    let syncChecks = 0;
    let nextPeriodicSyncTick = system.currentTick + 100;
'''
    if state_anchor not in js:
        raise RuntimeError("Item Mic 2.6.6 pending range state anchor missing")
    js = js.replace(state_anchor, state_replacement, 1)

    old_submit = '''      if (!requestVoiceRange(player, value)) {
        rangeConfirmText.setData("สถานะระยะเสียง: §cส่งคำขอไม่สำเร็จ§r");
        return;
      }

      pendingRange = value;
      pendingChecks = 0;
      customRange.setData(String(value));
'''
    new_submit = '''      const requestId = requestVoiceRange(player, value);
      if (!requestId) {
        rangeConfirmText.setData("สถานะระยะเสียง: §cส่งคำขอไม่สำเร็จ§r");
        return;
      }

      pendingRange = value;
      pendingRequestId = requestId;
      pendingChecks = 0;
      syncRequestId = "";
      syncChecks = 0;
      customRange.setData(String(value));
'''
    if old_submit not in js:
        raise RuntimeError("Item Mic 2.6.6 submitRange anchor missing")
    js = js.replace(old_submit, new_submit, 1)

    refresh_start = js.index("    refreshId = system.runInterval(() => {", js.index("async function showSettings(player) {"))
    refresh_end = js.index("\n    await form.show();", refresh_start)
    old_refresh = js[refresh_start:refresh_end]

    new_refresh = r'''    refreshId = system.runInterval(() => {
      try {
        const refreshed = stateFor(player);
        const nextMax = Math.max(1, currentMaxRange(player));

        statusText.setData(
          `สถานะไมค์: ${refreshed.effective ? "§aON" : "§cOFF"}§r`
        );
        modeText.setData(
          `โหมด: §e${modeUiLabel(refreshed.mode)}§r`
        );
        rangeText.setData(
          `ระยะเสียงปัจจุบัน: §b${confirmedRange} บล็อก§r`
        );
        offhandText.setData(
          isMicId(getOffId(player))
            ? "มือซ้าย: §aMic อยู่มือซ้าย — บังคับ ON§r"
            : "มือซ้าย: §7ไม่มี Mic§r"
        );
        serverLimitText.setData(
          isOperator(player)
            ? "สิทธิ์: §dOperator — ไม่จำกัด§r"
            : `ระยะสูงสุด: §b${nextMax} บล็อก§r`
        );
        holdDisabled.setData(refreshed.mode === MODE_HOLD);
        toggleDisabled.setData(refreshed.mode === MODE_TOGGLE);

        sliderMax.setData(nextMax);
        if (rangeSlider.getData() > nextMax && !isOperator(player)) {
          rangeSlider.setData(nextMax);
        }

        if (pendingRequestId) {
          const ack = consumeVoiceRangeAck(player, pendingRequestId);
          if (ack) {
            if (ack.value >= 1) {
              confirmedRange = ack.value;
              player.setDynamicProperty(PROP_VOICE_RANGE, confirmedRange);
              rangeText.setData(
                `ระยะเสียงปัจจุบัน: §b${confirmedRange} บล็อก§r`
              );
              customRange.setData(String(confirmedRange));
              if (isOperator(player) || confirmedRange <= nextMax) {
                rangeSlider.setData(Math.min(confirmedRange, nextMax));
              }
            }

            if (ack.status === "ok" && ack.value === pendingRange) {
              rangeConfirmText.setData(
                `สถานะระยะเสียง: §aเซิร์ฟเวอร์ยืนยันแล้ว — ${ack.value} บล็อก§r`
              );
            } else {
              rangeConfirmText.setData(
                `สถานะระยะเสียง: §cเซิร์ฟเวอร์ไม่รับค่าที่ขอ — ใช้ ${confirmedRange} บล็อก§r`
              );
            }

            pendingRange = null;
            pendingRequestId = "";
            pendingChecks = 0;
            nextPeriodicSyncTick = system.currentTick + 100;
          } else {
            pendingChecks++;
            if (pendingChecks >= 80) {
              rangeConfirmText.setData(
                `สถานะระยะเสียง: §6ยังไม่ได้รับการยืนยัน ${pendingRange} บล็อก§r`
              );
            }
          }
        } else {
          if (!syncRequestId && system.currentTick >= nextPeriodicSyncTick) {
            syncRequestId = requestVoiceRangeSync(player);
            syncChecks = 0;
            nextPeriodicSyncTick = system.currentTick + 100;
          }

          if (syncRequestId) {
            const syncAck = consumeVoiceRangeAck(player, syncRequestId);
            if (syncAck) {
              if (syncAck.value >= 1) {
                confirmedRange = syncAck.value;
                player.setDynamicProperty(PROP_VOICE_RANGE, confirmedRange);
                rangeText.setData(
                  `ระยะเสียงปัจจุบัน: §b${confirmedRange} บล็อก§r`
                );
                customRange.setData(String(confirmedRange));
                if (isOperator(player) || confirmedRange <= nextMax) {
                  rangeSlider.setData(Math.min(confirmedRange, nextMax));
                }
              }
              syncRequestId = "";
              syncChecks = 0;
              nextPeriodicSyncTick = system.currentTick + 100;
            } else {
              syncChecks++;
              if (syncChecks >= 80) {
                syncRequestId = "";
                syncChecks = 0;
                nextPeriodicSyncTick = system.currentTick + 100;
              }
            }
          }
        }
      } catch (e) {
        console.warn(
          "[VoiceCraftItem/BP] Voice Range DDUI refresh failed player=" +
          player.name + ": " + e
        );
      }
    }, 5);'''

    js = js[:refresh_start] + new_refresh + js[refresh_end:]

    js = js.replace(
        "[VoiceCraftItem/BP] Loaded v2.6.5 — immediate submit-close + reliable Bind fallback",
        "[VoiceCraftItem/BP] Loaded v2.6.6 — authoritative Voice Range ACK sync + stable Bind",
        1,
    )

    required = [
        "voicecraft.vr.ack.",
        "voicecraft.vr.sync.",
        "nextRangeRequestId",
        "consumeVoiceRangeAck",
        "requestVoiceRangeSync",
        'player.addTag(`${RANGE_REQUEST_PREFIX}${requestId}.${value}`)',
        "pendingRequestId",
        "confirmedRange",
        'ack.status === "ok"',
        "เซิร์ฟเวอร์ยืนยันแล้ว",
        "เซิร์ฟเวอร์ไม่รับค่าที่ขอ",
        "Voice Range DDUI refresh failed",
        "Loaded v2.6.6",
        "openBindFromMic",
        "submittedCloseRequested",
        "form.close()",
    ]
    missing = [value for value in required if value not in js]
    if missing:
        raise RuntimeError(f"Item Mic 2.6.6 ACK patch failed: {missing}")

    forbidden = [
        'player.addTag(`${RANGE_REQUEST_PREFIX}${value}`)',
        "syncVoiceRangeFromServer(player);\n        const refreshed",
        "confirmedServerRange === pendingRange",
        "Loaded v2.6.5",
    ]
    leftovers = [value for value in forbidden if value in js]
    if leftovers:
        raise RuntimeError(f"Unexpected legacy Voice Range flow in 2.6.6: {leftovers}")

    return js


def main() -> None:
    repo = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
    output = Path(
        sys.argv[2]
        if len(sys.argv) > 2
        else "release-assets/VoiceCraft_ItemMic_v2.6.6_DDUI-Bind.mcaddon"
    )
    if not output.is_absolute():
        output = repo / output

    logo = repo / "VoiceCraft.Guest.Patch/VoiceCraft.Server.Android/Resources/drawable/voicecraft_logo.webp"
    if not logo.exists():
        raise SystemExit(f"VoiceCraft logo not found: {logo}")

    files = dict(base.TEXT_FILES)
    files["BP/manifest.json"] = patch_manifest(
        files["BP/manifest.json"],
        "VoiceCraft Item Mic BP v2.6.6 DDUI Bind",
        "Stable Bind DDUI plus authoritative Voice Range request/ACK synchronization.",
    )
    files["RP/manifest.json"] = patch_manifest(
        files["RP/manifest.json"],
        "VoiceCraft Mic Icons RP v2.6.6",
        "Inventory icons plus invisible held Mic model for VoiceCraft Item Mic v2.6.6.",
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
    with tempfile.TemporaryDirectory(prefix="voicecraft-itemmic-2.6.6-ddui-bind-") as td:
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

        rp_pack = tmp / "VoiceCraft_ItemMic_RP_v2.6.6.mcpack"
        bp_pack = tmp / "VoiceCraft_ItemMic_BP_v2.6.6.mcpack"
        base.zip_dir(rp, rp_pack)
        base.zip_dir(bp, bp_pack)

        with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.write(rp_pack, rp_pack.name)
            zf.write(bp_pack, bp_pack.name)

    print(output)


if __name__ == "__main__":
    main()
