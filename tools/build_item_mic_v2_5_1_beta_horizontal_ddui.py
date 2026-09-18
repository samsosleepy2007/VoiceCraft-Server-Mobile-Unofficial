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

VERSION = [2, 5, 1]
SERVER_UI_BETA = "2.4.0-beta.1.26.60-preview.25"
SERVER_BETA = "2.12.0-beta.1.26.60-preview.25"

BP_HEADER_UUID = "46951783-7b21-4d1e-9ed9-5165a18291e7"
BP_DATA_MODULE_UUID = "02d3164f-688b-4f01-a6d4-a06928235595"
BP_SCRIPT_MODULE_UUID = "0734df19-fbd9-44ad-804b-2399bcd85d34"
RP_HEADER_UUID = "472b0285-0ae2-4192-81be-576adbba30d3"
RP_MODULE_UUID = "a4579a61-8320-4c40-9c34-4d068d0408be"


def patch_manifest(text: str, pack: str) -> str:
    data = json.loads(text)
    data["header"]["version"] = VERSION
    data["header"]["min_engine_version"] = [1, 26, 60]

    if pack == "BP":
        data["header"]["name"] = "VoiceCraft Item Mic BP v2.5.1-beta Horizontal DDUI"
        data["header"]["description"] = (
            "Experimental horizontal DDUI using multiButtonRow. "
            "Preview/Beta build; keep separate from the stable Item Mic pack."
        )
        data["header"]["uuid"] = BP_HEADER_UUID

        for module in data.get("modules", []):
            module["version"] = VERSION
            if module.get("type") == "data":
                module["uuid"] = BP_DATA_MODULE_UUID
            elif module.get("type") == "script":
                module["uuid"] = BP_SCRIPT_MODULE_UUID

        for dependency in data.get("dependencies", []):
            if dependency.get("module_name") == "@minecraft/server":
                dependency["version"] = SERVER_BETA
            elif dependency.get("module_name") == "@minecraft/server-ui":
                dependency["version"] = SERVER_UI_BETA
            elif dependency.get("uuid") == "cb345edb-6e6c-49ac-9950-e2ae07bda214":
                dependency["uuid"] = RP_HEADER_UUID
                dependency["version"] = VERSION
    elif pack == "RP":
        data["header"]["name"] = "VoiceCraft Mic Icons RP v2.5.1-beta Horizontal"
        data["header"]["description"] = (
            "Experimental resource pack for Item Mic v2.5.1-beta Horizontal DDUI."
        )
        data["header"]["uuid"] = RP_HEADER_UUID
        for module in data.get("modules", []):
            module["version"] = VERSION
            if module.get("type") == "resources":
                module["uuid"] = RP_MODULE_UUID
    else:
        raise ValueError(f"Unknown pack kind: {pack}")

    return json.dumps(data, ensure_ascii=False, indent=2) + "\n"


def patch_script(js: str) -> str:
    js = stable.patch_script(js)

    old_mode = r'''.label("Hold-to-Talk\nถือ Mic เพื่อเปิดไมค์ และจะปิดอัตโนมัติเมื่อเปลี่ยนช่องหรือเลิกถือ")
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
    .label("Toggle\nถือ Mic หนึ่งครั้งเพื่อเปิดไมค์ จากนั้นเปลี่ยนช่องได้โดยไมค์ยังเปิดอยู่ และถือ Mic อีกครั้งเพื่อปิด")
    .button("Toggle", () => {
      applyMicModeFromUi(
        player,
        MODE_TOGGLE,
        statusText,
        modeText,
        holdDisabled,
        toggleDisabled
      );
    }, { disabled: toggleDisabled })'''

    new_mode = r'''.label("Hold-to-Talk\nถือ Mic เพื่อเปิดไมค์ และจะปิดอัตโนมัติเมื่อเปลี่ยนช่องหรือเลิกถือ")
    .spacer()
    .label("Toggle\nถือ Mic หนึ่งครั้งเพื่อเปิดไมค์ จากนั้นเปลี่ยนช่องได้โดยไมค์ยังเปิดอยู่ และถือ Mic อีกครั้งเพื่อปิด")
    .multiButtonRow([
      {
        label: "Hold-to-Talk",
        onClick: () => {
          applyMicModeFromUi(
            player,
            MODE_HOLD,
            statusText,
            modeText,
            holdDisabled,
            toggleDisabled
          );
        },
        options: { disabled: holdDisabled },
      },
      {
        label: "Toggle",
        onClick: () => {
          applyMicModeFromUi(
            player,
            MODE_TOGGLE,
            statusText,
            modeText,
            holdDisabled,
            toggleDisabled
          );
        },
        options: { disabled: toggleDisabled },
      },
    ])'''

    if old_mode not in js:
        raise RuntimeError("Horizontal beta patch anchor missing: Mic Mode buttons")
    js = js.replace(old_mode, new_mode, 1)

    old_range = r'''.button("5 บล็อก", () => {
      applyVoiceRangeFromUi(player, 5, rangeText, customRange);
    })
    .button("10 บล็อก", () => {
      applyVoiceRangeFromUi(player, 10, rangeText, customRange);
    })
    .button("20 บล็อก", () => {
      applyVoiceRangeFromUi(player, 20, rangeText, customRange);
    })'''

    new_range = r'''.multiButtonRow([
      {
        label: "5 บล็อก",
        onClick: () => {
          applyVoiceRangeFromUi(player, 5, rangeText, customRange);
        },
      },
      {
        label: "10 บล็อก",
        onClick: () => {
          applyVoiceRangeFromUi(player, 10, rangeText, customRange);
        },
      },
      {
        label: "20 บล็อก",
        onClick: () => {
          applyVoiceRangeFromUi(player, 20, rangeText, customRange);
        },
      },
    ])'''

    if old_range not in js:
        raise RuntimeError("Horizontal beta patch anchor missing: Voice Range buttons")
    js = js.replace(old_range, new_range, 1)

    js = js.replace(
        "[VoiceCraftItem/BP] Loaded v2.5.2 — DDUI help text + hidden held model + single Mic enforcement + Voice Range",
        "[VoiceCraftItem/BP] Loaded v2.5.1-beta — Horizontal DDUI multiButtonRow + Voice Range",
        1,
    )

    required = [
        ".multiButtonRow([",
        'label: "Hold-to-Talk"',
        'label: "Toggle"',
        'label: "5 บล็อก"',
        'label: "10 บล็อก"',
        'label: "20 บล็อก"',
        "options: { disabled: holdDisabled }",
        "options: { disabled: toggleDisabled }",
        "Loaded v2.5.1-beta",
        "CustomForm",
        "ObservableBoolean",
        "voicecraft.vr.request.",
    ]
    missing = [value for value in required if value not in js]
    if missing:
        raise RuntimeError(f"Horizontal beta DDUI patch failed: {missing}")

    # Stable vertical buttons must be gone for the two horizontal groups.
    forbidden = [
        '.button("Hold-to-Talk",',
        '.button("Toggle",',
        '.button("5 บล็อก",',
        '.button("10 บล็อก",',
        '.button("20 บล็อก",',
    ]
    leftovers = [value for value in forbidden if value in js]
    if leftovers:
        raise RuntimeError(f"Vertical button API remains in horizontal beta: {leftovers}")

    return js


def main() -> None:
    repo = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
    output = Path(
        sys.argv[2]
        if len(sys.argv) > 2
        else "release-assets/VoiceCraft_ItemMic_v2.5.1-beta_Horizontal-DDUI.mcaddon"
    )
    if not output.is_absolute():
        output = repo / output

    logo = repo / "VoiceCraft.Guest.Patch/VoiceCraft.Server.Android/Resources/drawable/voicecraft_logo.webp"
    if not logo.exists():
        raise SystemExit(f"VoiceCraft logo not found: {logo}")

    files = dict(base.TEXT_FILES)
    files["BP/manifest.json"] = patch_manifest(files["BP/manifest.json"], "BP")
    files["RP/manifest.json"] = patch_manifest(files["RP/manifest.json"], "RP")

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
    with tempfile.TemporaryDirectory(prefix="voicecraft-itemmic-2.5.1-beta-horizontal-") as td:
        tmp = Path(td)
        bp = tmp / "BP"
        rp = tmp / "RP"

        for rel, file_content in files.items():
            path = tmp / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(file_content, encoding="utf-8")

        items = rp / "textures/items"
        items.mkdir(parents=True, exist_ok=True)
        (items / "icon_mic_off.png").write_bytes(__import__("base64").b64decode(base.ICON_OFF_B64))
        (items / "icon_mic_on.png").write_bytes(__import__("base64").b64decode(base.ICON_ON_B64))

        entity_textures = rp / "textures/entity"
        entity_textures.mkdir(parents=True, exist_ok=True)
        Image.new("RGBA", (1, 1), (0, 0, 0, 0)).save(
            entity_textures / "voicecraft_mic_invisible.png", "PNG"
        )

        with Image.open(logo) as image:
            rgba = image.convert("RGBA")
            rgba.save(bp / "pack_icon.png", "PNG")
            rgba.save(rp / "pack_icon.png", "PNG")

        rp_pack = tmp / "VoiceCraft_ItemMic_RP_v2.5.1-beta-Horizontal.mcpack"
        bp_pack = tmp / "VoiceCraft_ItemMic_BP_v2.5.1-beta-Horizontal.mcpack"
        base.zip_dir(rp, rp_pack)
        base.zip_dir(bp, bp_pack)

        with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.write(rp_pack, rp_pack.name)
            zf.write(bp_pack, bp_pack.name)

    print(output)


if __name__ == "__main__":
    main()
