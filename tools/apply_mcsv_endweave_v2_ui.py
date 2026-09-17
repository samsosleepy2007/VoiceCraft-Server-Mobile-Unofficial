#!/usr/bin/env python3
from pathlib import Path
import subprocess
import sys


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"MCSV Endweave V2 UI anchor mismatch ({count}): {label}")
    return text.replace(old, new, 1)


def main() -> None:
    repo = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
    activity = repo / "VoiceCraft.Server.Android" / "ModernMainActivity.cs"
    if not activity.exists():
        raise SystemExit(f"ModernMainActivity.cs not found: {activity}")

    text = activity.read_text(encoding="utf-8")

    text = replace_once(
        text,
        '"ใส่ MCSV API Key แล้วแอปจะติดตั้ง VoiceCraft Addon และ Endstone Plugin ให้อัตโนมัติ เขียน Relay Config ให้ครบ และ Restart เซิร์ฟเวอร์หลังติดตั้งเสร็จ",\n'
        '                "Enter an MCSV API key and the app installs the VoiceCraft add-on and Endstone plugin, writes the Relay config, then restarts the server automatically."',
        '"ใส่ MCSV API Key แล้วแอปจะตรวจ OS/Python เลือก Endweave ให้ตรงเซิร์ฟเวอร์ ติดตั้ง Endweave + VoiceCraft Plugin + Item Mic เขียน Config/World Packs แล้ว Restart และตรวจ Startup Log อัตโนมัติ",\n'
        '                "Enter an MCSV API key and the app detects OS/Python, selects the matching Endweave wheel, installs Endweave + VoiceCraft + Item Mic, writes config/world packs, restarts, and verifies startup logs automatically."',
        "MCSV card V2 description",
    )

    text = replace_once(
        text,
        'T("เชื่อม MCSV และติดตั้ง VoiceCraft", "Connect MCSV & Install VoiceCraft")',
        'T("เชื่อม MCSV และติดตั้ง VoiceCraft + Endweave", "Connect MCSV & Install VoiceCraft + Endweave")',
        "setup title",
    )

    text = replace_once(
        text,
        'T("Key ต้องเป็น “สิทธิ์เต็ม” เพื่อให้ติดตั้งไฟล์ แตกไฟล์ แก้ config และ Restart เซิร์ฟเวอร์ได้", "Use a Full access key so VoiceCraft can install/extract files, update config, and restart the server.")',
        'T("Key ต้องเป็น “สิทธิ์เต็ม” เพื่อให้ตรวจ Runtime ติดตั้งไฟล์ แก้ Config/World Packs อ่าน Startup Log และ Restart เซิร์ฟเวอร์ได้", "Use a Full access key so VoiceCraft can inspect the runtime, install files, update config/world packs, read startup logs, and restart the server.")',
        "Full access V2 explanation",
    )

    text = replace_once(
        text,
        'T("ติดตั้ง / อัปเดต VoiceCraft", "INSTALL / UPDATE VOICECRAFT")',
        'T("ติดตั้ง / อัปเดต VoiceCraft + Endweave", "INSTALL / UPDATE VOICECRAFT + ENDWEAVE")',
        "saved-token action label",
    )

    text = replace_once(
        text,
        'SetMcsvStatus(T("● ติดตั้งสำเร็จ", "● Installation complete"), Green);',
        'SetMcsvStatus(T("● Endweave + VoiceCraft พร้อมใช้งาน", "● Endweave + VoiceCraft ready"), Green);',
        "Ready status",
    )

    text = replace_once(
        text,
        '.SetTitle(T("ติดตั้ง VoiceCraft สำเร็จ", "VoiceCraft installed"))',
        '.SetTitle(T("Endweave + VoiceCraft พร้อมใช้งาน", "Endweave + VoiceCraft ready"))',
        "success dialog title",
    )

    activity.write_text(text, encoding="utf-8")

    final = activity.read_text(encoding="utf-8")
    required = [
        "ตรวจ OS/Python",
        "matching Endweave wheel",
        "VoiceCraft + Endweave",
        "อ่าน Startup Log",
        "Endweave + VoiceCraft พร้อมใช้งาน",
        "Endweave + VoiceCraft ready",
    ]
    missing = [marker for marker in required if marker not in final]
    if missing:
        raise RuntimeError(f"MCSV Endweave V2 UI validation failed: {missing}")

    logging_patch = repo / "tools" / "apply_mcsv_install_logging.py"
    if not logging_patch.exists():
        raise RuntimeError(f"MCSV detailed logging patch is missing: {logging_patch}")
    subprocess.run(
        [sys.executable, str(logging_patch), str(repo)],
        check=True,
    )

    installer = repo / "VoiceCraft.Server.Android" / "McsvVoiceCraftInstaller.cs"
    logger = repo / "VoiceCraft.Server.Android" / "McsvInstallLogger.cs"
    generated_installer = installer.read_text(encoding="utf-8")
    generated_activity = activity.read_text(encoding="utf-8")
    if "MCSV_INSTALL_DETAILED_LOGGING" not in generated_installer:
        raise RuntimeError("MCSV detailed installer logging marker was not generated")
    if not logger.exists():
        raise RuntimeError("MCSV install logger was not copied into the Android project")
    if "MCSV INSTALL, OK, WARN, ERROR" not in generated_activity:
        raise RuntimeError("Diagnostics UI does not advertise MCSV installer log states")

    print(f"Applied MCSV Endweave V2 UI to {activity}")
    print("Applied detailed MCSV installer logging")


if __name__ == "__main__":
    main()
