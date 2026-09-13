#!/usr/bin/env python3
from pathlib import Path
import re
import subprocess
import sys

DISPLAY_VERSION = "1.7.1-android-phase2-ui4.5.2-account-v2-guest"
VERSION_CODE = 13


def sub_required(text: str, pattern: str, replacement: str, label: str) -> str:
    changed, count = re.subn(pattern, replacement, text, count=1, flags=re.S)
    if count != 1:
        raise RuntimeError(f"Could not apply legal compliance patch: {label}")
    return changed


def patch_main_activity(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    if "ShowOpenSourceLegal" not in text:
        account_action = '''        app.AddView(SettingsAction(
            T("บัญชี", "Account"),
            T("ดูบัญชีที่ใช้งาน สลับ Free Account หรือออกจากระบบ", "View the active account, switch to Free Account, or log out"),
            T("จัดการ", "MANAGE"),
            OpenAccountCenter), Top(Dp(8)));'''
        legal_action = account_action + '''
        app.AddView(SettingsAction(
            T("โอเพนซอร์สและข้อกำหนด", "Open Source & Legal"),
            T("เครดิต VoiceCraft ต้นฉบับ, source code และ GPL-3.0", "VoiceCraft upstream credit, source code and GPL-3.0"),
            T("ดู", "VIEW"),
            ShowOpenSourceLegal), Top(Dp(8)));'''
        if account_action not in text:
            raise RuntimeError("Could not apply legal compliance patch: Settings Account action")
        text = text.replace(account_action, legal_action, 1)

        marker = "    private void ShowInformation()"
        legal_methods = '''    private void ShowOpenSourceLegal()
    {
        var message = T(
            "VoiceCraft Server Mobile เป็นงานดัดแปลงแบบไม่เป็นทางการที่พัฒนาต่อยอดจาก VoiceCraft ของ AvionBlock\\n\\n" +
            "ต้นฉบับ: AvionBlock/VoiceCraft\\n" +
            "เวอร์ชันฐาน: VoiceCraft v1.7.1\\n" +
            "สัญญาอนุญาต: GNU GPL v3\\n\\n" +
            "โปรเจกต์นี้เพิ่ม Android server hosting, Endstone bridge, Render relay/failover, Account/Free Account และ UI สำหรับมือถือ โดยไม่ได้อ้างว่าเป็น Release อย่างเป็นทางการของ AvionBlock\\n\\n" +
            "สามารถเปิด source ของโปรเจกต์, source ต้นฉบับ และ GPL-3.0 ได้จากปุ่มด้านล่าง",
            "VoiceCraft Server Mobile is an unofficial modified distribution based on VoiceCraft by AvionBlock.\\n\\n" +
            "Upstream: AvionBlock/VoiceCraft\\n" +
            "Base version: VoiceCraft v1.7.1\\n" +
            "License: GNU GPL v3\\n\\n" +
            "This project adds Android server hosting, the Endstone bridge, Render relay/failover, Account/Free Account and a mobile UI. It is not presented as an official AvionBlock release.\\n\\n" +
            "Use the buttons below to open this project's source, the upstream project, or the GPL-3.0 license.");

        new AlertDialog.Builder(this)
            .SetTitle(T("โอเพนซอร์สและข้อกำหนด", "Open Source & Legal"))
            .SetMessage(message)
            .SetPositiveButton(T("SOURCE โปรเจกต์", "PROJECT SOURCE"), (_, _) => OpenLegalUrl("https://github.com/samsosleepy2007/VoiceCraft-Server-Mobile-Unofficial"))
            .SetNeutralButton(T("VOICECRAFT ต้นฉบับ", "VOICECRAFT UPSTREAM"), (_, _) => OpenLegalUrl("https://github.com/AvionBlock/VoiceCraft"))
            .SetNegativeButton("GPL-3.0", (_, _) => OpenLegalUrl("https://github.com/samsosleepy2007/VoiceCraft-Server-Mobile-Unofficial/blob/main/LICENSE.md"))
            .Show();
    }

    private void OpenLegalUrl(string url)
    {
        try
        {
            var intent = new Intent(Intent.ActionView, global::Android.Net.Uri.Parse(url));
            StartActivity(intent);
        }
        catch (Exception ex)
        {
            AndroidRuntimeLog.Append("UI", $"Unable to open legal URL: {ex.Message}");
            Toast.MakeText(this, T("ไม่สามารถเปิดลิงก์ได้", "Unable to open link"), ToastLength.Short)?.Show();
        }
    }

'''
        if marker not in text:
            raise RuntimeError("Could not apply legal compliance patch: ShowInformation marker")
        text = text.replace(marker, legal_methods + marker, 1)
    path.write_text(text, encoding="utf-8")


def patch_version(android: Path) -> None:
    csproj = android / "VoiceCraft.Server.Android.csproj"
    text = csproj.read_text(encoding="utf-8")
    text = re.sub(r"<ApplicationVersion>\d+</ApplicationVersion>", f"<ApplicationVersion>{VERSION_CODE}</ApplicationVersion>", text)
    text = re.sub(r"<ApplicationDisplayVersion>[^<]+</ApplicationDisplayVersion>", f"<ApplicationDisplayVersion>{DISPLAY_VERSION}</ApplicationDisplayVersion>", text)
    csproj.write_text(text, encoding="utf-8")

    version_pattern = re.compile(r"1\.7\.1-android-phase2-ui4\.[0-9]+(?:\.[0-9]+)?(?:-[A-Za-z0-9._-]+)?")
    for path in android.glob("*.cs"):
        source = path.read_text(encoding="utf-8")
        changed = version_pattern.sub(DISPLAY_VERSION, source)
        if changed != source:
            path.write_text(changed, encoding="utf-8")


def run_if_present(repo: Path, relative: str) -> None:
    script = repo / relative
    if script.exists():
        subprocess.run([sys.executable, str(script), str(repo)], check=True)


def main() -> None:
    if len(sys.argv) != 2:
        print("Usage: python apply_legal_compliance_patch.py <VoiceCraft-Server-Mobile repo root>")
        raise SystemExit(2)

    repo = Path(sys.argv[1]).resolve()
    android = repo / "VoiceCraft.Server.Android"
    if not android.is_dir():
        raise SystemExit(f"Android project not found: {android}")
    main_activity = android / "ModernMainActivity.cs"
    if not main_activity.exists():
        raise SystemExit(f"ModernMainActivity not found: {main_activity}")

    patch_main_activity(main_activity)
    patch_version(android)

    run_if_present(repo, "tools/apply_ui5_figma_redesign.py")
    run_if_present(repo, "tools/fix_ui5_generated_newlines.py")
    run_if_present(repo, "tools/apply_ui5_refinement.py")
    run_if_present(repo, "tools/apply_ui5_polish.py")
    run_if_present(repo, "tools/apply_dashboard_profile_avatar.py")
    run_if_present(repo, "tools/apply_render_api_core.py")
    run_if_present(repo, "tools/apply_render_relay_setup.py")
    run_if_present(repo, "tools/apply_render_security_hardening.py")
    run_if_present(repo, "tools/fix_ui5_generated_newlines.py")
    run_if_present(repo, "tools/validate_render_relay_security.py")

    print("Legal/Open Source patch applied.")
    print(f"Android display version: {DISPLAY_VERSION}")
    print(f"Android version code: {VERSION_CODE}")
    print("Settings now exposes Project Source, VoiceCraft Upstream and GPL-3.0.")


if __name__ == "__main__":
    main()
