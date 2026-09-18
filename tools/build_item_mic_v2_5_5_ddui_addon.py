#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import json
import sys
import tempfile
import zipfile

from PIL import Image

import build_item_mic_addon as base
import build_item_mic_v2_5_ddui_addon as stable

VERSION = [2, 5, 5]


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
    js = stable.patch_script(js)

    js = js.replace(
        'import { CustomForm, ObservableBoolean, ObservableString } from "@minecraft/server-ui";',
        'import { CustomForm, ObservableBoolean, ObservableNumber, ObservableString } from "@minecraft/server-ui";',
        1,
    )

    start = js.index("async function showSettings(player) {")
    end = js.index("\nsystem.beforeEvents.startup.subscribe", start)

    replacement = r'''const openSettingsPlayers = new Set();

async function showSettings(player) {
  if (openSettingsPlayers.has(player.id)) {
    player.sendMessage("§e[VoiceCraft] หน้าตั้งค่า Mic เปิดอยู่แล้ว§r");
    return;
  }

  openSettingsPlayers.add(player.id);
  let refreshId;

  try {
    ensureMic(player);
    evaluate(player);
    syncVoiceRangeFromServer(player);

    const initial = stateFor(player);
    const initialRange = currentVoiceRange(player);
    const initialMax = Math.max(1, currentMaxRange(player));

    const statusText = new ObservableString(
      `สถานะไมค์: ${initial.effective ? "§aON" : "§cOFF"}§r`
    );
    const modeText = new ObservableString(
      `โหมด: §e${modeUiLabel(initial.mode)}§r`
    );
    const rangeText = new ObservableString(
      `ระยะเสียงปัจจุบัน: §b${initialRange} บล็อก§r`
    );
    const rangeConfirmText = new ObservableString(
      "สถานะระยะเสียง: §aพร้อมใช้งาน§r"
    );
    const offhandText = new ObservableString(
      isMicId(getOffId(player))
        ? "มือซ้าย: §aMic อยู่มือซ้าย — บังคับ ON§r"
        : "มือซ้าย: §7ไม่มี Mic§r"
    );
    const serverLimitText = new ObservableString(
      isOperator(player)
        ? "สิทธิ์: §dOperator — ไม่จำกัด§r"
        : `ระยะสูงสุด: §b${initialMax} บล็อก§r`
    );

    const holdDisabled = new ObservableBoolean(initial.mode === MODE_HOLD);
    const toggleDisabled = new ObservableBoolean(initial.mode === MODE_TOGGLE);
    const advancedVisible = new ObservableBoolean(false, {
      clientWritable: true,
    });
    const rangeSlider = new ObservableNumber(
      Math.min(initialRange, initialMax),
      { clientWritable: true }
    );
    const sliderMax = new ObservableNumber(initialMax);
    const customRange = new ObservableString(String(initialRange), {
      clientWritable: true,
    });

    let pendingRange = null;
    let pendingChecks = 0;

    const submitRange = (rawValue) => {
      const value = Number.parseInt(String(rawValue ?? ""), 10);
      if (!Number.isFinite(value)) {
        rangeConfirmText.setData("สถานะระยะเสียง: §cกรุณาระบุเป็นตัวเลข§r");
        return;
      }

      if (!requestVoiceRange(player, value)) {
        rangeConfirmText.setData("สถานะระยะเสียง: §cส่งคำขอไม่สำเร็จ§r");
        return;
      }

      pendingRange = value;
      pendingChecks = 0;
      customRange.setData(String(value));

      const maxNow = sliderMax.getData();
      if (value >= 1 && value <= maxNow) {
        rangeSlider.setData(value);
      }

      rangeConfirmText.setData(
        `สถานะระยะเสียง: §eกำลังรอเซิร์ฟเวอร์ยืนยัน ${value} บล็อก...§r`
      );
      player.sendMessage(
        `§e[VoiceCraft] ส่งคำขอตั้งระยะเสียง ${value} บล็อกไปยังเซิร์ฟเวอร์แล้ว§r`
      );
    };

    const form = new CustomForm(player, "VoiceCraft • Mic Settings")
      .label(statusText)
      .spacer()
      .label(modeText)
      .spacer()
      .label(rangeText)
      .spacer()
      .label(offhandText)
      .spacer()
      .label(serverLimitText)
      .spacer()
      .divider()
      .header("Mic Mode")
      .label("เลือกรูปแบบการเปิดและปิดไมค์")
      .spacer()
      .label("Hold-to-Talk")
      .spacer()
      .label("ถือ Mic เพื่อเปิดไมค์")
      .spacer()
      .label("เลิกถือหรือเปลี่ยนช่องเพื่อปิดไมค์")
      .spacer()
      .button("Hold-to-Talk", () => {
        applyMicModeFromUi(
          player,
          MODE_HOLD,
          statusText,
          modeText,
          holdDisabled,
          toggleDisabled
        );
      }, { disabled: holdDisabled })
      .spacer()
      .label("Toggle")
      .spacer()
      .label("ถือ Mic หนึ่งครั้งเพื่อเปิดไมค์")
      .spacer()
      .label("ถือ Mic อีกครั้งเพื่อปิดไมค์")
      .spacer()
      .button("Toggle", () => {
        applyMicModeFromUi(
          player,
          MODE_TOGGLE,
          statusText,
          modeText,
          holdDisabled,
          toggleDisabled
        );
      }, { disabled: toggleDisabled })
      .spacer()
      .divider()
      .header("Voice Range")
      .label(rangeConfirmText)
      .spacer()
      .button("5 บล็อก", () => submitRange(5))
      .button("10 บล็อก", () => submitRange(10))
      .button("20 บล็อก", () => submitRange(20))
      .spacer()
      .slider(
        "ระยะเสียงแบบ Slider",
        rangeSlider,
        1,
        sliderMax,
        {
          step: 1,
          description: "กำหนดระยะที่ผู้เล่นอื่นจะได้ยินเสียงของคุณ • เลื่อนเพื่อเลือกระยะอย่างรวดเร็ว แล้วกดใช้ระยะจาก Slider",
        }
      )
      .button("ใช้ระยะจาก Slider", () => {
        submitRange(rangeSlider.getData());
      })
      .spacer()
      .toggle(
        "การตั้งค่าขั้นสูง",
        advancedVisible,
        {
          description: "เปิดเพื่อกรอกระยะเสียงเองแบบละเอียด",
        }
      )
      .textField(
        "กำหนดระยะเอง (บล็อก)",
        customRange,
        {
          visible: advancedVisible,
          description: isOperator(player)
            ? "Operator สามารถกรอกระยะเกิน Limit ของเซิร์ฟเวอร์ได้"
            : "ค่าต้องไม่เกินระยะสูงสุดของเซิร์ฟเวอร์",
        }
      )
      .button("ใช้ระยะที่กำหนด", () => {
        submitRange(customRange.getData());
      }, { visible: advancedVisible })
      .spacer()
      .divider()
      .header("Reset")
      .label("คืนค่า Mic Mode เป็น Hold-to-Talk")
      .spacer()
      .label("Voice Range จะกลับเป็น 20 บล็อก")
      .spacer()
      .button("คืนค่าเริ่มต้น", () => {
        const resetRange = isOperator(player)
          ? 20
          : Math.min(20, sliderMax.getData());
        advancedVisible.setData(false);
        customRange.setData(String(resetRange));
        rangeSlider.setData(Math.min(resetRange, sliderMax.getData()));
        applyMicModeFromUi(
          player,
          MODE_HOLD,
          statusText,
          modeText,
          holdDisabled,
          toggleDisabled
        );
        submitRange(resetRange);
      })
      .spacer()
      .closeButton();

    refreshId = system.runInterval(() => {
      try {
        syncVoiceRangeFromServer(player);
        const refreshed = stateFor(player);
        const actualRange = currentVoiceRange(player);
        const confirmedServerRange = readTaggedNumber(
          player,
          RANGE_VALUE_PREFIX,
          0
        );
        const nextMax = Math.max(1, currentMaxRange(player));

        statusText.setData(
          `สถานะไมค์: ${refreshed.effective ? "§aON" : "§cOFF"}§r`
        );
        modeText.setData(
          `โหมด: §e${modeUiLabel(refreshed.mode)}§r`
        );
        rangeText.setData(
          `ระยะเสียงปัจจุบัน: §b${actualRange} บล็อก§r`
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

        const sliderValue = rangeSlider.getData();
        if (sliderValue > nextMax) {
          rangeSlider.setData(nextMax);
        }
        sliderMax.setData(nextMax);

        if (pendingRange !== null) {
          if (confirmedServerRange === pendingRange) {
            rangeConfirmText.setData(
              `สถานะระยะเสียง: §aเซิร์ฟเวอร์ยืนยันแล้ว — ${confirmedServerRange} บล็อก§r`
            );
            customRange.setData(String(confirmedServerRange));
            if (confirmedServerRange <= nextMax) {
              rangeSlider.setData(confirmedServerRange);
            }
            pendingRange = null;
            pendingChecks = 0;
          } else {
            pendingChecks++;
            if (pendingChecks >= 40) {
              rangeConfirmText.setData(
                `สถานะระยะเสียง: §6ยังไม่ได้รับการยืนยัน ${pendingRange} บล็อก§r`
              );
            }
          }
        }
      } catch {}
    }, 5);

    await form.show();
  } catch (e) {
    console.warn(
      `[VoiceCraftItem/BP] DDUI form failed player=${player.name}: ${e}`
    );
  } finally {
    if (refreshId !== undefined) {
      system.clearRun(refreshId);
    }
    openSettingsPlayers.delete(player.id);
  }
}
'''

    js = js[:start] + replacement + js[end:]

    js = js.replace(
        "[VoiceCraftItem/BP] Loaded v2.5.2 — DDUI help text + hidden held model + single Mic enforcement + Voice Range",
        "[VoiceCraftItem/BP] Loaded v2.5.5 — spaced Mic Mode and Reset descriptions + stable DDUI controls",
        1,
    )

    required = [
        "ObservableNumber",
        'สถานะไมค์: ${initial.effective ? "§aON" : "§cOFF"}§r',
        'โหมด: §e${modeUiLabel(initial.mode)}§r',
        'ระยะเสียงปัจจุบัน: §b${initialRange} บล็อก§r',
        "เลือกรูปแบบการเปิดและปิดไมค์",
        "Hold-to-Talk",
        "ถือ Mic เพื่อเปิดไมค์",
        "เลิกถือหรือเปลี่ยนช่องเพื่อปิดไมค์",
        "Toggle",
        "ถือ Mic หนึ่งครั้งเพื่อเปิดไมค์",
        "ถือ Mic อีกครั้งเพื่อปิดไมค์",
        "กำหนดระยะที่ผู้เล่นอื่นจะได้ยินเสียงของคุณ • เลื่อนเพื่อเลือกระยะอย่างรวดเร็ว",
        "คืนค่า Mic Mode เป็น Hold-to-Talk",
        "Voice Range จะกลับเป็น 20 บล็อก",
        "const openSettingsPlayers = new Set()",
        "openSettingsPlayers.has(player.id)",
        "new ObservableNumber",
        ".slider(",
        '"ระยะเสียงแบบ Slider"',
        ".toggle(",
        '"การตั้งค่าขั้นสูง"',
        "visible: advancedVisible",
        '"ใช้ระยะจาก Slider"',
        '"คืนค่าเริ่มต้น"',
        "pendingRange",
        "confirmedServerRange",
        "readTaggedNumber",
        "RANGE_VALUE_PREFIX",
        "resetRange",
        "เซิร์ฟเวอร์ยืนยันแล้ว",
        "ยังไม่ได้รับการยืนยัน",
        "Loaded v2.5.5",
        "voicecraft.vr.request.",
        "MIC_DUPLICATE_REMOVED",
    ]
    missing = [value for value in required if value not in js]
    if missing:
        raise RuntimeError(f"Item Mic 2.5.5 DDUI patch failed: {missing}")

    forbidden = [
        "ActionFormData",
        "ModalFormData",
        ".show(player)",
        "response.selection",
        "response.formValues",
        "VoiceCraft Voice Chat",
        "DDUI อัปเดตสถานะบนหน้าจอนี้แบบ real-time โดยไม่ต้องปิดเมนู",
        "multiButtonRow",
    ]
    leftovers = [value for value in forbidden if value in js]
    if leftovers:
        raise RuntimeError(f"Unexpected API remains in Item Mic 2.5.5: {leftovers}")

    return js


def main() -> None:
    repo = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
    output = Path(
        sys.argv[2]
        if len(sys.argv) > 2
        else "release-assets/VoiceCraft_ItemMic_v2.5.5_DDUI.mcaddon"
    )
    if not output.is_absolute():
        output = repo / output

    logo = repo / "VoiceCraft.Guest.Patch/VoiceCraft.Server.Android/Resources/drawable/voicecraft_logo.webp"
    if not logo.exists():
        raise SystemExit(f"VoiceCraft logo not found: {logo}")

    files = dict(base.TEXT_FILES)
    files["BP/manifest.json"] = patch_manifest(
        files["BP/manifest.json"],
        "VoiceCraft Item Mic BP v2.5.5 DDUI",
        "Stable DDUI Mic settings with spaced Mic Mode and Reset descriptions, Voice Range slider, advanced controls and server confirmation.",
    )
    files["RP/manifest.json"] = patch_manifest(
        files["RP/manifest.json"],
        "VoiceCraft Mic Icons RP v2.5.5",
        "Inventory icons plus invisible held Mic model for VoiceCraft Item Mic v2.5.5 DDUI.",
    )

    for path in (
        "BP/items/mic_hold.item.json",
        "BP/items/mic_toggle.item.json",
        "BP/items/mic_off.item.json",
        "BP/items/mic_on.item.json",
    ):
        files[path] = stable.hide_from_creative(files[path])

    files["BP/scripts/main.js"] = patch_script(files["BP/scripts/main.js"])

    files["RP/models/entity/voicecraft_mic_invisible.geo.json"] = stable.INVISIBLE_GEOMETRY
    files["RP/render_controllers/voicecraft_mic_invisible.render_controllers.json"] = stable.INVISIBLE_RENDER_CONTROLLER
    files["RP/attachables/mic_off.entity.json"] = stable.attachable("voicecraft:mic_off")
    files["RP/attachables/mic_on.entity.json"] = stable.attachable("voicecraft:mic_on")
    files["RP/attachables/mic_hold.entity.json"] = stable.attachable("voicecraft:mic_hold")
    files["RP/attachables/mic_toggle.entity.json"] = stable.attachable("voicecraft:mic_toggle")

    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="voicecraft-itemmic-2.5.5-ddui-") as td:
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

        rp_pack = tmp / "VoiceCraft_ItemMic_RP_v2.5.5.mcpack"
        bp_pack = tmp / "VoiceCraft_ItemMic_BP_v2.5.5.mcpack"
        base.zip_dir(rp, rp_pack)
        base.zip_dir(bp, bp_pack)

        with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.write(rp_pack, rp_pack.name)
            zf.write(bp_pack, bp_pack.name)

    print(output)


if __name__ == "__main__":
    main()
