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
import build_item_mic_v2_6_8_ddui_bind_addon as previous

VERSION = [2, 6, 9]


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

    old_sets = """const openBindPlayers = new Set();
const bindLastOpenToken = new Map();
const bindRetryAfterTick = new Map();
const bindCheckPendingByPlayer = new Map();
let bindCheckSequence = 0;"""
    new_sets = """const openBindPlayers = new Set();
const bindLastOpenToken = new Map();
const bindRetryAfterTick = new Map();
const bindCheckPendingByPlayer = new Map();
const bindMicWithheldPlayers = new Set();
const bindMicRestoreSlots = new Map();
let bindCheckSequence = 0;"""
    if old_sets not in js:
        raise RuntimeError("Item Mic 2.6.9 Bind Mic state anchor missing")
    js = js.replace(old_sets, new_sets, 1)

    ensure_anchor = """function ensureMic(player) {
  enforceSingleMic(player);
  if (hasAnyMic(player)) return;
"""
    ensure_replacement = r'''function rememberMicRestoreSlot(player) {
  if (bindMicRestoreSlots.has(player.id)) return;

  const inv = inventory(player);
  if (inv) {
    let selected = -1;
    try {
      selected = Number(player.selectedSlotIndex);
    } catch {}

    if (
      Number.isInteger(selected) &&
      selected >= 0 &&
      selected < inv.size &&
      isMicId(itemId(inv.getItem(selected)))
    ) {
      bindMicRestoreSlots.set(player.id, selected);
      return;
    }

    for (let i = 0; i < inv.size; i++) {
      if (isMicId(itemId(inv.getItem(i)))) {
        bindMicRestoreSlots.set(player.id, i);
        return;
      }
    }
  }

  if (isMicId(getOffId(player))) {
    bindMicRestoreSlots.set(player.id, -1);
  }
}

function removeAllMicsForBind(player) {
  rememberMicRestoreSlot(player);

  let removed = 0;
  const inv = inventory(player);
  if (inv) {
    for (let i = 0; i < inv.size; i++) {
      if (!isMicId(itemId(inv.getItem(i)))) continue;
      inv.setItem(i, undefined);
      removed++;
    }
  }

  try {
    const eq = equippable(player);
    const off = eq?.getEquipment(EquipmentSlot.Offhand);
    if (isMicId(itemId(off))) {
      eq.setEquipment(EquipmentSlot.Offhand, undefined);
      removed++;
    }
  } catch (e) {
    console.warn(
      "[VoiceCraftItem/BP] bind Mic offhand remove failed player=" +
      player.name + ": " + e
    );
  }

  setLatch(player, false);
  states.delete(player.id);

  if (removed > 0) {
    console.warn(
      "[VoiceCraftItem/BP] MIC_WITHHELD_FOR_BIND player=" +
      player.name + " removed=" + removed
    );
  }

  return removed;
}

function withholdMicForBind(player) {
  bindMicWithheldPlayers.add(player.id);
  removeAllMicsForBind(player);
}

function restoreMicAfterBind(player) {
  if (!bindMicWithheldPlayers.delete(player.id)) return false;

  const restoreSlot = bindMicRestoreSlots.get(player.id);
  bindMicRestoreSlots.delete(player.id);

  setLatch(player, false);
  states.delete(player.id);

  let restored = false;
  const inv = inventory(player);

  // Prefer the inventory slot where the Mic was removed.
  if (
    inv &&
    Number.isInteger(restoreSlot) &&
    restoreSlot >= 0 &&
    restoreSlot < inv.size &&
    !inv.getItem(restoreSlot)
  ) {
    try {
      inv.setItem(restoreSlot, makeMic(false));
      restored = true;
    } catch {}
  }

  // Otherwise let Minecraft choose any free inventory slot.
  if (!restored && inv) {
    try {
      const leftover = inv.addItem(makeMic(false));
      restored = !leftover;
    } catch {}
  }

  // If the Mic was originally only in offhand and inventory became full,
  // returning it to offhand is safer than losing the player's Mic.
  if (!restored && restoreSlot === -1) {
    try {
      equippable(player)?.setEquipment(
        EquipmentSlot.Offhand,
        makeMic(false)
      );
      restored = isMicId(getOffId(player));
    } catch {}
  }

  if (restored) {
    reassertMicFlags(player);
    console.warn(
      "[VoiceCraftItem/BP] MIC_RETURNED_AFTER_BIND player=" + player.name
    );
  } else {
    player.sendMessage(
      "§c[VoiceCraft] Bind สำเร็จแล้ว แต่ Inventory เต็ม — ไม่สามารถคืน Mic ได้§r"
    );
  }

  states.delete(player.id);
  return restored;
}

function syncMicWithBindState(player) {
  const state = bindState(player);

  if (state === "bound") {
    if (bindMicWithheldPlayers.has(player.id)) {
      restoreMicAfterBind(player);
    }
    return;
  }

  if (bindMicWithheldPlayers.has(player.id)) {
    // Base Item Mic code calls ensureMic repeatedly. Keep removing any Mic
    // that might be reintroduced while a Bind is still required/pending.
    removeAllMicsForBind(player);
  }
}

function ensureMic(player) {
  enforceSingleMic(player);
  if (bindMicWithheldPlayers.has(player.id)) {
    removeAllMicsForBind(player);
    return;
  }
  if (hasAnyMic(player)) return;
'''
    if ensure_anchor not in js:
        raise RuntimeError("Item Mic 2.6.9 ensureMic anchor missing")
    js = js.replace(ensure_anchor, ensure_replacement, 1)

    show_anchor = """async function showBindDdui(player, openToken) {
  if (openBindPlayers.has(player.id)) return;

  openBindPlayers.add(player.id);
"""
    show_replacement = """async function showBindDdui(player, openToken) {
  if (openBindPlayers.has(player.id)) return;

  // Never take the Mic from a player that is already authoritatively bound.
  if (bindState(player) === "bound") {
    restoreMicAfterBind(player);
    return;
  }

  // Once Bind UI is actually requested, the Mic is withheld until Endstone
  // publishes authoritative bound state.
  withholdMicForBind(player);
  openBindPlayers.add(player.id);
"""
    if show_anchor not in js:
        raise RuntimeError("Item Mic 2.6.9 showBindDdui anchor missing")
    js = js.replace(show_anchor, show_replacement, 1)

    bound_refresh_anchor = """        if (state === "bound") {
          bindingKey.setData("");
"""
    bound_refresh_replacement = """        if (state === "bound") {
          restoreMicAfterBind(player);
          bindingKey.setData("");
"""
    if bound_refresh_anchor not in js:
        raise RuntimeError("Item Mic 2.6.9 Bind form bound anchor missing")
    js = js.replace(bound_refresh_anchor, bound_refresh_replacement, 1)

    route_bound_anchor = """  if (state === "bound") {
    showSettings(player);
    return;
  }
"""
    route_bound_replacement = """  if (state === "bound") {
    restoreMicAfterBind(player);
    showSettings(player);
    return;
  }
"""
    if route_bound_anchor not in js:
        raise RuntimeError("Item Mic 2.6.9 authoritative route bound anchor missing")
    js = js.replace(route_bound_anchor, route_bound_replacement, 1)

    poll_anchor = """function pollBindDdui(player) {
  ensureBindDduiReady(player);

  const token = getTagValue(player, BIND_OPEN_PREFIX);
"""
    poll_replacement = """function pollBindDdui(player) {
  ensureBindDduiReady(player);
  syncMicWithBindState(player);

  const token = getTagValue(player, BIND_OPEN_PREFIX);
"""
    if poll_anchor not in js:
        raise RuntimeError("Item Mic 2.6.9 pollBindDdui anchor missing")
    js = js.replace(poll_anchor, poll_replacement, 1)

    spawn_anchor = """      bindCheckPendingByPlayer.delete(player.id);
      clearBindCheckTags(player);
      removeTagsByPrefix(player, BIND_UI_CLOSED_PREFIX);"""
    spawn_replacement = """      bindCheckPendingByPlayer.delete(player.id);
      bindMicWithheldPlayers.delete(player.id);
      bindMicRestoreSlots.delete(player.id);
      clearBindCheckTags(player);
      removeTagsByPrefix(player, BIND_UI_CLOSED_PREFIX);"""
    if spawn_anchor not in js:
        raise RuntimeError("Item Mic 2.6.9 spawn cleanup anchor missing")
    js = js.replace(spawn_anchor, spawn_replacement, 1)

    leave_anchor = """  bindRetryAfterTick.delete(ev.playerId);
  bindCheckPendingByPlayer.delete(ev.playerId);
});"""
    leave_replacement = """  bindRetryAfterTick.delete(ev.playerId);
  bindCheckPendingByPlayer.delete(ev.playerId);
  bindMicWithheldPlayers.delete(ev.playerId);
  bindMicRestoreSlots.delete(ev.playerId);
});"""
    if leave_anchor not in js:
        raise RuntimeError("Item Mic 2.6.9 leave cleanup anchor missing")
    js = js.replace(leave_anchor, leave_replacement, 1)

    js = js.replace(
        "[VoiceCraftItem/BP] Loaded v2.6.8 — Endstone Bind check handshake + Voice Range ACK sync",
        "[VoiceCraftItem/BP] Loaded v2.6.9 — Mic withheld during Bind + authoritative Endstone state",
        1,
    )

    required = [
        "bindMicWithheldPlayers",
        "bindMicRestoreSlots",
        "rememberMicRestoreSlot",
        "removeAllMicsForBind",
        "withholdMicForBind",
        "restoreMicAfterBind",
        "syncMicWithBindState",
        "MIC_WITHHELD_FOR_BIND",
        "MIC_RETURNED_AFTER_BIND",
        "eq.setEquipment(EquipmentSlot.Offhand, undefined)",
        'if (bindState(player) === "bound")',
        "syncMicWithBindState(player);",
        "voicecraft.bind.check.",
        "voicecraft.bind.check_result.",
        "voicecraft.vr.ack.",
        "voicecraft.vr.sync.",
        "submittedCloseRequested",
        "Loaded v2.6.9",
    ]
    missing = [value for value in required if value not in js]
    if missing:
        raise RuntimeError(f"Item Mic 2.6.9 Bind Mic lifecycle patch failed: {missing}")

    return js


def main() -> None:
    repo = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
    output = Path(
        sys.argv[2]
        if len(sys.argv) > 2
        else "release-assets/VoiceCraft_ItemMic_v2.6.9_DDUI-Bind.mcaddon"
    )
    if not output.is_absolute():
        output = repo / output

    logo = repo / "VoiceCraft.Guest.Patch/VoiceCraft.Server.Android/Resources/drawable/voicecraft_logo.webp"
    if not logo.exists():
        raise SystemExit(f"VoiceCraft logo not found: {logo}")

    files = dict(base.TEXT_FILES)
    files["BP/manifest.json"] = patch_manifest(
        files["BP/manifest.json"],
        "VoiceCraft Item Mic BP v2.6.9 DDUI Bind",
        "Mic withheld while Binding, returned after authoritative Bind success, with Endstone Bind check and Voice Range ACK.",
    )
    files["RP/manifest.json"] = patch_manifest(
        files["RP/manifest.json"],
        "VoiceCraft Mic Icons RP v2.6.9",
        "Inventory icons plus invisible held Mic model for VoiceCraft Item Mic v2.6.9.",
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
    with tempfile.TemporaryDirectory(prefix="voicecraft-itemmic-2.6.9-ddui-bind-") as td:
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

        rp_pack = tmp / "VoiceCraft_ItemMic_RP_v2.6.9.mcpack"
        bp_pack = tmp / "VoiceCraft_ItemMic_BP_v2.6.9.mcpack"
        base.zip_dir(rp, rp_pack)
        base.zip_dir(bp, bp_pack)

        with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.write(rp_pack, rp_pack.name)
            zf.write(bp_pack, bp_pack.name)

    print(output)


if __name__ == "__main__":
    main()
