#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import json
import sys
import tempfile
import zipfile

from PIL import Image

import build_item_mic_addon as base
import build_item_mic_voice_range_addon as vr

VERSION = [2, 4, 0]

MIC_IDS = (
    "voicecraft:mic_off",
    "voicecraft:mic_on",
    "voicecraft:mic_hold",
    "voicecraft:mic_toggle",
)


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


def hide_from_creative(text: str) -> str:
    data = json.loads(text)
    description = data["minecraft:item"]["description"]
    description["menu_category"] = {"category": "none"}
    return json.dumps(data, ensure_ascii=False, indent=2) + "\n"


def patch_script(js: str) -> str:
    js = vr.patch_script(js)

    anchor = '''function hasAnyMic(player) {
  return scanMic(player).length > 0;
}
'''
    replacement = r'''function enforceSingleMic(player) {
  const inv = inventory(player);
  const offMic = isMicId(getOffId(player));
  let keepIndex = -1;

  // Preserve the offhand Mic first because offhand intentionally forces Mic ON.
  if (!offMic && inv) {
    let selected = -1;
    try {
      selected = Number(player.selectedSlotIndex);
    } catch {}
    if (Number.isInteger(selected) && selected >= 0 && selected < inv.size) {
      if (isMicId(itemId(inv.getItem(selected)))) keepIndex = selected;
    }
    if (keepIndex < 0) {
      for (let i = 0; i < inv.size; i++) {
        if (isMicId(itemId(inv.getItem(i)))) {
          keepIndex = i;
          break;
        }
      }
    }
  }

  let removed = 0;
  if (inv) {
    for (let i = 0; i < inv.size; i++) {
      if (!isMicId(itemId(inv.getItem(i)))) continue;
      if (!offMic && i === keepIndex) continue;
      inv.setItem(i, undefined);
      removed++;
    }
  }

  if (removed > 0) {
    console.warn(`[VoiceCraftItem/BP] MIC_DUPLICATE_REMOVED player=${player.name} removed=${removed} kept=${offMic ? "offhand" : keepIndex}`);
  }
  return removed;
}

function hasAnyMic(player) {
  return scanMic(player).length > 0;
}
'''
    if anchor not in js:
        raise RuntimeError("Item Mic 2.4 patch anchor missing: hasAnyMic")
    js = js.replace(anchor, replacement, 1)

    js = js.replace(
        '''function ensureMic(player) {
  if (hasAnyMic(player)) return;
''',
        '''function ensureMic(player) {
  enforceSingleMic(player);
  if (hasAnyMic(player)) return;
''',
        1,
    )

    js = js.replace(
        '''function evaluate(player) {
  migrateLegacy(player);
  ensureMic(player);
''',
        '''function evaluate(player) {
  migrateLegacy(player);
  enforceSingleMic(player);
  ensureMic(player);
''',
        1,
    )

    js = js.replace(
        '[VoiceCraftItem/BP] Loaded v2.3.0 — Mic modes + server-authoritative Voice Range',
        '[VoiceCraftItem/BP] Loaded v2.4.0 — hidden held model + single Mic enforcement + Voice Range',
        1,
    )

    required = [
        "enforceSingleMic(player)",
        "MIC_DUPLICATE_REMOVED",
        "selectedSlotIndex",
        "inv.setItem(i, undefined)",
        "Loaded v2.4.0",
        "voicecraft.vr.request.",
    ]
    missing = [value for value in required if value not in js]
    if missing:
        raise RuntimeError(f"Item Mic 2.4 script patch failed: {missing}")
    return js


def attachable(identifier: str) -> str:
    data = {
        "format_version": "1.10.0",
        "minecraft:attachable": {
            "description": {
                "identifier": identifier,
                "materials": {"default": "entity_alphatest"},
                "textures": {"default": "textures/entity/voicecraft_mic_invisible"},
                "geometry": {"default": "geometry.voicecraft.mic_invisible"},
                "render_controllers": ["controller.render.voicecraft_mic_invisible"],
            }
        },
    }
    return json.dumps(data, ensure_ascii=False, indent=2) + "\n"


INVISIBLE_GEOMETRY = '''{
  "format_version": "1.12.0",
  "minecraft:geometry": [
    {
      "description": {
        "identifier": "geometry.voicecraft.mic_invisible",
        "texture_width": 1,
        "texture_height": 1,
        "visible_bounds_width": 0.01,
        "visible_bounds_height": 0.01,
        "visible_bounds_offset": [0, 0, 0]
      },
      "bones": [
        {
          "name": "root",
          "pivot": [0, 0, 0],
          "cubes": []
        }
      ]
    }
  ]
}
'''

INVISIBLE_RENDER_CONTROLLER = '''{
  "format_version": "1.8.0",
  "render_controllers": {
    "controller.render.voicecraft_mic_invisible": {
      "geometry": "Geometry.default",
      "materials": [
        { "*": "Material.default" }
      ],
      "textures": ["Texture.default"]
    }
  }
}
'''


def main() -> None:
    repo = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
    output = Path(sys.argv[2] if len(sys.argv) > 2 else "release-assets/VoiceCraft_ItemMic_v2.4.0.mcaddon")
    if not output.is_absolute():
        output = repo / output

    logo = repo / "VoiceCraft.Guest.Patch/VoiceCraft.Server.Android/Resources/drawable/voicecraft_logo.webp"
    if not logo.exists():
        raise SystemExit(f"VoiceCraft logo not found: {logo}")

    files = dict(base.TEXT_FILES)
    files["BP/manifest.json"] = patch_manifest(
        files["BP/manifest.json"],
        "VoiceCraft Item Mic BP v2.4",
        "Single hidden Mic item, Hold/Toggle modes, offhand always-on and Voice Range UI.",
    )
    files["RP/manifest.json"] = patch_manifest(
        files["RP/manifest.json"],
        "VoiceCraft Mic Icons RP v2.4",
        "Inventory icons plus invisible held Mic model for VoiceCraft Item Mic v2.4.",
    )

    for path in (
        "BP/items/mic_hold.item.json",
        "BP/items/mic_toggle.item.json",
        "BP/items/mic_off.item.json",
        "BP/items/mic_on.item.json",
    ):
        files[path] = hide_from_creative(files[path])

    files["BP/scripts/main.js"] = patch_script(files["BP/scripts/main.js"])

    files["RP/models/entity/voicecraft_mic_invisible.geo.json"] = INVISIBLE_GEOMETRY
    files["RP/render_controllers/voicecraft_mic_invisible.render_controllers.json"] = INVISIBLE_RENDER_CONTROLLER
    files["RP/attachables/mic_off.entity.json"] = attachable("voicecraft:mic_off")
    files["RP/attachables/mic_on.entity.json"] = attachable("voicecraft:mic_on")
    files["RP/attachables/mic_hold.entity.json"] = attachable("voicecraft:mic_hold")
    files["RP/attachables/mic_toggle.entity.json"] = attachable("voicecraft:mic_toggle")

    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="voicecraft-itemmic-2.4-") as td:
        tmp = Path(td)
        bp = tmp / "BP"
        rp = tmp / "RP"
        for rel, content in files.items():
            path = tmp / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")

        items = rp / "textures/items"
        items.mkdir(parents=True, exist_ok=True)
        (items / "icon_mic_off.png").write_bytes(__import__("base64").b64decode(base.ICON_OFF_B64))
        (items / "icon_mic_on.png").write_bytes(__import__("base64").b64decode(base.ICON_ON_B64))

        entity_textures = rp / "textures/entity"
        entity_textures.mkdir(parents=True, exist_ok=True)
        Image.new("RGBA", (1, 1), (0, 0, 0, 0)).save(entity_textures / "voicecraft_mic_invisible.png", "PNG")

        with Image.open(logo) as image:
            rgba = image.convert("RGBA")
            rgba.save(bp / "pack_icon.png", "PNG")
            rgba.save(rp / "pack_icon.png", "PNG")

        rp_pack = tmp / "VoiceCraft_ItemMic_RP_v2.4.0.mcpack"
        bp_pack = tmp / "VoiceCraft_ItemMic_BP_v2.4.0.mcpack"
        base.zip_dir(rp, rp_pack)
        base.zip_dir(bp, bp_pack)
        with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.write(rp_pack, rp_pack.name)
            zf.write(bp_pack, bp_pack.name)

    print(output)


if __name__ == "__main__":
    main()
