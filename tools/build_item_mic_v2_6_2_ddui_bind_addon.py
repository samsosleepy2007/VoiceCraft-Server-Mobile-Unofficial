#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import json
import sys
import tempfile
import zipfile

from PIL import Image

import build_item_mic_addon as base
import build_item_mic_v2_5_5_ddui_addon as previous

VERSION = [2, 6, 2]


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

    anchor = "\nsystem.beforeEvents.startup.subscribe"
    if anchor not in js:
        raise RuntimeError("Item Mic 2.6.2 bind DDUI anchor missing")

    binding_code = r'''
const BIND_DDUI_READY_TAG = "voicecraft.bind.ddui.ready";
const BIND_STATE_PREFIX = "voicecraft.bind.state.";
const BIND_OPEN_PREFIX = "voicecraft.bind.open.";
const BIND_REQUEST_PREFIX = "voicecraft.bind.request.";
const BIND_ERROR_PREFIX = "voicecraft.bind.error.";
const BIND_UI_CLOSED_PREFIX = "voicecraft.bind.ui.closed.";

const openBindPlayers = new Set();
const bindLastOpenToken = new Map();
const bindRetryAfterTick = new Map();

function getTagValue(player, prefix) {
  try {
    for (const tag of player.getTags()) {
      if (tag.startsWith(prefix)) return tag.slice(prefix.length);
    }
  } catch {}
  return "";
}

function removeTagsByPrefix(player, prefix) {
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

function reportBindUiClosed(player, openToken) {
  if (!openToken) return;
  removeTagsByPrefix(player, BIND_UI_CLOSED_PREFIX);
  try {
    player.addTag(BIND_UI_CLOSED_PREFIX + openToken);
  } catch (e) {
    console.warn("[VoiceCraftItem/BP] bind close ack failed player=" + player.name + ": " + e);
  }
}

function closeReasonName(reason) {
  try {
    return String(reason ?? "");
  } catch {
    return "";
  }
}

function ensureBindDduiReady(player) {
  try {
    if (!player.hasTag(BIND_DDUI_READY_TAG)) {
      player.addTag(BIND_DDUI_READY_TAG);
    }
  } catch {}
}

function bindState(player) {
  return getTagValue(player, BIND_STATE_PREFIX) || "unbound";
}

function bindError(player) {
  return getTagValue(player, BIND_ERROR_PREFIX);
}

function bindStatusText(player) {
  const state = bindState(player);
  const error = bindError(player);

  if (state === "bound") {
    return "สถานะ: §aเชื่อมต่อไมโครโฟนแล้ว§r";
  }
  if (state === "pending") {
    return "สถานะ: §eกำลังตรวจสอบ Binding Key...§r";
  }
  if (state === "reconnecting") {
    return "สถานะ: §eการเชื่อมต่อหลุด — กำลังเชื่อมต่อกลับอัตโนมัติ...§r";
  }
  if (state === "rebind_required") {
    return "สถานะ: §6ต้องเชื่อมต่อใหม่ — กรุณากรอก Binding Key ใหม่§r";
  }
  if (state === "disconnecting") {
    return "สถานะ: §eกำลังยกเลิกการเชื่อมต่อ...§r";
  }
  if (state === "error") {
    if (error === "invalid_key") {
      return "สถานะ: §cBinding Key ไม่ถูกต้อง ถูกใช้ไปแล้ว หรือหมดอายุ§r";
    }
    if (error === "client_disconnected") {
      return "สถานะ: §cVoiceCraft Client หลุด กรุณาเชื่อมต่อเซิร์ฟเวอร์ไมค์ใหม่§r";
    }
    if (error === "server_mode_required") {
      return "สถานะ: §cกรุณาตั้ง Positioning Type ใน VoiceCraft เป็น Server§r";
    }
    if (error === "empty_key") {
      return "สถานะ: §cกรุณากรอก Binding Key§r";
    }
    if (error === "invalid_length") {
      return "สถานะ: §cBinding Key มีความยาวไม่ถูกต้อง§r";
    }
    return "สถานะ: §cเชื่อมต่อไม่สำเร็จ กรุณาตรวจสอบ Binding Key แล้วลองใหม่§r";
  }
  return "สถานะ: §6ยังไม่ได้เชื่อมต่อไมโครโฟน§r";
}

function submitBindingKey(player, rawValue, statusText) {
  const key = String(rawValue ?? "").trim();

  if (!key) {
    statusText.setData("สถานะ: §cกรุณากรอก Binding Key§r");
    return;
  }
  if (key.length < 4 || key.length > 128) {
    statusText.setData("สถานะ: §cBinding Key มีความยาวไม่ถูกต้อง§r");
    return;
  }
  if (!/^[A-Za-z0-9]+$/.test(key)) {
    statusText.setData("สถานะ: §cBinding Key ใช้ได้เฉพาะตัวอักษรภาษาอังกฤษและตัวเลข§r");
    return;
  }

  removeTagsByPrefix(player, BIND_REQUEST_PREFIX);
  try {
    player.addTag(BIND_REQUEST_PREFIX + key);
    statusText.setData("สถานะ: §eกำลังส่ง Binding Key ไปยังเซิร์ฟเวอร์...§r");
  } catch (e) {
    statusText.setData("สถานะ: §cไม่สามารถส่ง Binding Key ได้ กรุณาลองใหม่§r");
    console.warn("[VoiceCraftItem/BP] bind request failed player=" + player.name + ": " + e);
  }
}

async function showBindDdui(player, openToken) {
  if (openBindPlayers.has(player.id)) return;

  openBindPlayers.add(player.id);
  let refreshId;

  try {
    const statusText = new ObservableString(bindStatusText(player));
    const bindingKey = new ObservableString("", {
      clientWritable: true,
    });

    const form = new CustomForm(player, "VoiceCraft • BIND")
      .label(statusText)
      .spacer()
      .header("Binding Key")
      .textField(
        "",
        bindingKey,
        {
          description: "เชื่อมต่อเซิร์ฟเวอร์ไมค์ใน VoiceCraft ก่อน แล้วนำ Binding Key ที่แสดงมากรอกที่นี่",
        }
      )
      .button("เชื่อมต่อไมโครโฟน", () => {
        submitBindingKey(player, bindingKey.getData(), statusText);
      });

    refreshId = system.runInterval(() => {
      try {
        const state = bindState(player);
        statusText.setData(bindStatusText(player));
        if (state === "bound") {
          bindingKey.setData("");
          if (form.isShowing()) {
            system.run(() => {
              try {
                if (form.isShowing()) form.close();
              } catch (e) {
                console.warn("[VoiceCraftItem/BP] bind DDUI auto-close failed player=" + player.name + ": " + e);
              }
            });
          }
        }
      } catch {}
    }, 5);

    const closeReason = await form.show();
    const reasonName = closeReasonName(closeReason);
    const stateAfterClose = bindState(player);

    if (stateAfterClose !== "bound") {
      if (reasonName.includes("UserBusy")) {
        bindRetryAfterTick.set(player.id, system.currentTick + 20);
        bindLastOpenToken.delete(player.id);
      } else if (
        reasonName.includes("ClientClosed") ||
        reasonName.includes("UserClose") ||
        (!reasonName.includes("ServerClosed") && !reasonName.includes("ServerClose"))
      ) {
        reportBindUiClosed(player, openToken);
      }
    }
  } catch (e) {
    console.warn("[VoiceCraftItem/BP] bind DDUI failed player=" + player.name + ": " + e);
    bindRetryAfterTick.set(player.id, system.currentTick + 20);
    bindLastOpenToken.delete(player.id);
  } finally {
    if (refreshId !== undefined) {
      system.clearRun(refreshId);
    }
    openBindPlayers.delete(player.id);
  }
}

function pollBindDdui(player) {
  ensureBindDduiReady(player);

  const token = getTagValue(player, BIND_OPEN_PREFIX);
  if (!token) return;

  const previousToken = bindLastOpenToken.get(player.id);
  if (previousToken === token) return;

  const retryAt = bindRetryAfterTick.get(player.id) ?? 0;
  if (system.currentTick < retryAt) return;

  bindLastOpenToken.set(player.id, token);
  bindRetryAfterTick.delete(player.id);
  system.run(() => showBindDdui(player, token));
}

world.afterEvents.playerSpawn.subscribe((ev) => {
  const player = ev.player;
  system.run(() => {
    if (ev.initialSpawn === true) {
      openBindPlayers.delete(player.id);
      bindLastOpenToken.delete(player.id);
      bindRetryAfterTick.delete(player.id);
      removeTagsByPrefix(player, BIND_UI_CLOSED_PREFIX);
    }
    ensureBindDduiReady(player);
    pollBindDdui(player);
  });
});

world.afterEvents.playerLeave.subscribe((ev) => {
  openBindPlayers.delete(ev.playerId);
  bindLastOpenToken.delete(ev.playerId);
  bindRetryAfterTick.delete(ev.playerId);
});

system.runInterval(() => {
  for (const player of world.getAllPlayers()) {
    try {
      pollBindDdui(player);
    } catch (e) {
      console.warn("[VoiceCraftItem/BP] bind DDUI poll failed player=" + player.name + ": " + e);
    }
  }
}, 2);
'''

    js = js.replace(anchor, binding_code + anchor, 1)
    js = js.replace(
        "[VoiceCraftItem/BP] Loaded v2.5.5 — spaced Mic Mode and Reset descriptions + stable DDUI controls",
        "[VoiceCraftItem/BP] Loaded v2.6.2 — reliable Bind DDUI lifecycle + stable Mic DDUI",
        1,
    )

    required = [
        "voicecraft.bind.ddui.ready",
        "voicecraft.bind.state.",
        "voicecraft.bind.open.",
        "voicecraft.bind.request.",
        "voicecraft.bind.error.",
        "voicecraft.bind.ui.closed.",
        "reportBindUiClosed",
        "closeReasonName",
        "form.isShowing()",
        "form.close()",
        "ev.initialSpawn",
        "showBindDdui",
        "pollBindDdui",
        "submitBindingKey",
        "VoiceCraft • BIND",
        '.textField(\n        "",',
        "เชื่อมต่อเซิร์ฟเวอร์ไมค์ใน VoiceCraft ก่อน แล้วนำ Binding Key ที่แสดงมากรอกที่นี่",
        "กำลังเชื่อมต่อกลับอัตโนมัติ",
        "Binding Key ไม่ถูกต้อง ถูกใช้ไปแล้ว หรือหมดอายุ",
        "Loaded v2.6.2",
        "ObservableNumber",
        "CustomForm",
        "MIC_DUPLICATE_REMOVED",
        "voicecraft.vr.request.",
    ]
    missing = [value for value in required if value not in js]
    if missing:
        raise RuntimeError(f"Item Mic 2.6.2 bind DDUI patch failed: {missing}")

    forbidden = [
        "ActionFormData",
        "ModalFormData",
        "multiButtonRow",
        ".show(player)",
        "response.selection",
        "response.formValues",
        "VoiceCraft • เชื่อมต่อไมโครโฟน",
        "ถ้า VoiceCraft หลุด ระบบจะรอเชื่อมต่อกลับอัตโนมัติก่อน และจะแจ้งให้กรอก Key ใหม่เมื่อจำเป็น",
    ]
    leftovers = [value for value in forbidden if value in js]
    if leftovers:
        raise RuntimeError(f"Unexpected legacy/preview UI in Item Mic 2.6.2: {leftovers}")

    return js


def main() -> None:
    repo = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
    output = Path(
        sys.argv[2]
        if len(sys.argv) > 2
        else "release-assets/VoiceCraft_ItemMic_v2.6.2_DDUI-Bind.mcaddon"
    )
    if not output.is_absolute():
        output = repo / output

    logo = repo / "VoiceCraft.Guest.Patch/VoiceCraft.Server.Android/Resources/drawable/voicecraft_logo.webp"
    if not logo.exists():
        raise SystemExit(f"VoiceCraft logo not found: {logo}")

    files = dict(base.TEXT_FILES)
    files["BP/manifest.json"] = patch_manifest(
        files["BP/manifest.json"],
        "VoiceCraft Item Mic BP v2.6.2 DDUI Bind",
        "Stable Mic Settings DDUI plus reliable Endstone Binding Key DDUI lifecycle and reconnect/rebind status.",
    )
    files["RP/manifest.json"] = patch_manifest(
        files["RP/manifest.json"],
        "VoiceCraft Mic Icons RP v2.6.2",
        "Inventory icons plus invisible held Mic model for VoiceCraft Item Mic v2.6.2.",
    )

    for path in (
        "BP/items/mic_hold.item.json",
        "BP/items/mic_toggle.item.json",
        "BP/items/mic_off.item.json",
        "BP/items/mic_on.item.json",
    ):
        files[path] = previous.stable.hide_from_creative(files[path])

    files["BP/scripts/main.js"] = patch_script(files["BP/scripts/main.js"])

    files["RP/models/entity/voicecraft_mic_invisible.geo.json"] = previous.stable.INVISIBLE_GEOMETRY
    files["RP/render_controllers/voicecraft_mic_invisible.render_controllers.json"] = previous.stable.INVISIBLE_RENDER_CONTROLLER
    files["RP/attachables/mic_off.entity.json"] = previous.stable.attachable("voicecraft:mic_off")
    files["RP/attachables/mic_on.entity.json"] = previous.stable.attachable("voicecraft:mic_on")
    files["RP/attachables/mic_hold.entity.json"] = previous.stable.attachable("voicecraft:mic_hold")
    files["RP/attachables/mic_toggle.entity.json"] = previous.stable.attachable("voicecraft:mic_toggle")

    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="voicecraft-itemmic-2.6.2-ddui-bind-") as td:
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

        rp_pack = tmp / "VoiceCraft_ItemMic_RP_v2.6.2.mcpack"
        bp_pack = tmp / "VoiceCraft_ItemMic_BP_v2.6.2.mcpack"
        base.zip_dir(rp, rp_pack)
        base.zip_dir(bp, bp_pack)

        with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.write(rp_pack, rp_pack.name)
            zf.write(bp_pack, bp_pack.name)

    print(output)


if __name__ == "__main__":
    main()
