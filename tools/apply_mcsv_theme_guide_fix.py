#!/usr/bin/env python3
from pathlib import Path
import re
import shutil
import sys


def sub_required(text: str, pattern: str, replacement: str, label: str) -> str:
    updated, count = re.subn(pattern, replacement, text, count=1, flags=re.S)
    if count != 1:
        raise RuntimeError(f"MCSV theme/inline-help patch anchor missing: {label}")
    return updated


def copy_runtime_assets(repo: Path) -> None:
    src = repo / "VoiceCraft.Guest.Patch/VoiceCraft.Server.Android/ThemedDialogHelper.cs"
    dst = repo / "VoiceCraft.Server.Android/ThemedDialogHelper.cs"
    if not src.exists():
        raise RuntimeError(f"MCSV theme helper missing: {src}")
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def theme_all_android_dialogs(repo: Path) -> int:
    root = repo / "VoiceCraft.Server.Android"
    patterns = [
        ("new AlertDialog.Builder(this)", "VoiceCraft.Server.Android.ThemedDialogHelper.Builder(this)"),
        ("new AlertDialog.Builder(activity)", "VoiceCraft.Server.Android.ThemedDialogHelper.Builder(activity)"),
        ("new Android.App.AlertDialog.Builder(this)", "VoiceCraft.Server.Android.ThemedDialogHelper.Builder(this)"),
        ("new Android.App.AlertDialog.Builder(activity)", "VoiceCraft.Server.Android.ThemedDialogHelper.Builder(activity)"),
    ]
    total = 0
    for path in root.rglob("*.cs"):
        if path.name == "ThemedDialogHelper.cs":
            continue
        original = path.read_text(encoding="utf-8")
        updated = original
        for old, new in patterns:
            count = updated.count(old)
            total += count
            if count:
                updated = updated.replace(old, new)
        if updated != original:
            path.write_text(updated, encoding="utf-8")
    return total


def main() -> None:
    repo = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
    copy_runtime_assets(repo)
    activity = repo / "VoiceCraft.Server.Android/ModernMainActivity.cs"
    text = activity.read_text(encoding="utf-8")

    inline_help = r'''        _mcsvCard.AddView(mcsvDescription);

        var mcsvKeyHelp = Label(
            T(
                "วิธีสร้าง API Key:\n" +
                "1. เข้า MCSV แล้วกดเมนู API / MCP\n" +
                "2. กด “สร้าง key”\n" +
                "3. ตั้งชื่อ Key เช่น VoiceCraft\n" +
                "4. เลือก “สิทธิ์เต็ม” แล้วกด “สร้าง key”\n" +
                "5. กด Copy เพื่อคัดลอก Token ที่ขึ้นต้นด้วย mcsv_\n" +
                "6. กลับมาที่แอป กด “เชื่อม API และติดตั้ง” วาง Token ลงช่อง “MCSV API Key” แล้วกด “ติดตั้ง”\n\n" +
                "MCSV จะแสดง Token เพียงครั้งเดียว คัดลอกเก็บไว้ทันทีและอย่าส่งให้ผู้อื่น",
                "How to create an API key:\n" +
                "1. Open MCSV and select API / MCP\n" +
                "2. Tap Create key\n" +
                "3. Name the key, for example VoiceCraft\n" +
                "4. Choose Full access, then tap Create key\n" +
                "5. Tap Copy to copy the token beginning with mcsv_\n" +
                "6. Return to the app, tap CONNECT & INSTALL, paste the token into MCSV API Key, then tap INSTALL\n\n" +
                "MCSV shows the token only once. Save it immediately and never share it."),
            11,
            Ink);
        mcsvKeyHelp.SetPadding(Dp(12), Dp(10), Dp(12), Dp(10));
        mcsvKeyHelp.Background = Round(SurfaceSoft, 14, Border);
        _mcsvCard.AddView(mcsvKeyHelp, new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MatchParent, ViewGroup.LayoutParams.WrapContent) { TopMargin = Dp(8) });

        _mcsvCard.AddView(Label('''

    text = sub_required(
        text,
        r"        _mcsvCard\.AddView\(mcsvDescription\);\n\n        _mcsvCard\.AddView\(Label\(",
        inline_help,
        "inline API-key help below MCSV description",
    )

    text = sub_required(
        text,
        r'''\n        var mcsvGuideButton = MakeButton\(T\("ดูวิธีเอา API Key", "HOW TO GET API KEY"\)\);\n        WireButton\(mcsvGuideButton, ShowMcsvApiKeyGuide\);\n        _mcsvCard\.AddView\(mcsvGuideButton, new LinearLayout\.LayoutParams\(ViewGroup\.LayoutParams\.MatchParent, Dp\(48\)\) \{ TopMargin = Dp\(8\) \}\);\n''',
        "\n",
        "remove MCSV card guide button",
    )

    text = sub_required(
        text,
        r"    private void ShowMcsvApiKeyGuide\(\)\n    \{.*?\n    \}\n\n    private void ShowMcsvSetup\(\)",
        "    private void ShowMcsvSetup()",
        "remove API-key guide dialog",
    )

    setup_method = r'''    private void ShowMcsvSetup()
    {
        if (_mcsvBusy)
            return;
        if (!ValidateBridge(CurrentWebSocket(), CurrentServerId(), CurrentSecret(), out _))
        {
            Toast.MakeText(this, T("ตั้งค่า Render Relay, Server ID และ Secret ให้ครบก่อน", "Complete Render Relay, Server ID and Secret first"), ToastLength.Long)?.Show();
            return;
        }

        var hasSaved = McsvTokenStore.TryLoad(this, out var savedToken);
        var panel = new LinearLayout(this)
        {
            Orientation = Orientation.Vertical,
            Background = Solid(Surface)
        };
        panel.SetPadding(Dp(22), Dp(16), Dp(22), Dp(8));
        panel.AddView(Label(T("เชื่อม MCSV และติดตั้ง VoiceCraft", "Connect MCSV & Install VoiceCraft"), 18, Ink, true));
        var setupDescription = Label(
            T(
                "วาง Token ที่คัดลอกจาก MCSV ลงช่องด้านล่าง Token ต้องขึ้นต้นด้วย mcsv_ จากนั้นกด ติดตั้ง",
                "Paste the token copied from MCSV below. It must begin with mcsv_, then tap Install."),
            12,
            Ink);
        setupDescription.SetPadding(0, Dp(8), 0, Dp(6));
        panel.AddView(setupDescription);
        panel.AddView(InputLabel("MCSV API Key"));
        var apiKeyInput = Input(hasSaved ? savedToken : string.Empty, InputTypes.ClassText | InputTypes.TextVariationPassword);
        apiKeyInput.Hint = "mcsv_...";
        panel.AddView(apiKeyInput);
        panel.AddView(Label(
            T("Key ต้องเป็น “สิทธิ์เต็ม” เพื่อให้ติดตั้งไฟล์ แตกไฟล์ แก้ config และ Restart เซิร์ฟเวอร์ได้", "Use a Full access key so VoiceCraft can install/extract files, update config, and restart the server."),
            10,
            Muted));

        var builder = ThemedDialogHelper.Builder(this)
            .SetView(panel)
            .SetPositiveButton(T("ติดตั้ง", "INSTALL"), (_, _) =>
            {
                var token = apiKeyInput.Text?.Trim() ?? string.Empty;
                _ = RunMcsvInstallAsync(token);
            })
            .SetNegativeButton(T("ยกเลิก", "CANCEL"), (_, _) => { });

        if (hasSaved)
        {
            builder.SetNeutralButton(T("ลบ API Key", "REMOVE API KEY"), (_, _) =>
            {
                McsvTokenStore.Delete(this);
                RefreshMcsvCardVisibility(true);
                Toast.MakeText(this, T("ลบ MCSV API Key แล้ว", "MCSV API key removed"), ToastLength.Short)?.Show();
            });
        }
        var dialog = builder.Create();
        dialog.Show();
        ThemedDialogHelper.StyleShown(dialog, this);
    }

    private async Task RunMcsvInstallAsync'''

    text = sub_required(
        text,
        r"    private void ShowMcsvSetup\(\)\n    \{.*?\n    \}\n\n    private async Task RunMcsvInstallAsync",
        setup_method,
        "theme MCSV setup dialog without guide button",
    )

    activity.write_text(text, encoding="utf-8")
    replacements = theme_all_android_dialogs(repo)
    text = activity.read_text(encoding="utf-8")

    required = [
        "วิธีสร้าง API Key:",
        "เข้า MCSV แล้วกดเมนู API / MCP",
        "เลือก “สิทธิ์เต็ม”",
        "กด “เชื่อม API และติดตั้ง”",
        "วาง Token ลงช่อง “MCSV API Key”",
        "MCSV จะแสดง Token เพียงครั้งเดียว",
        "ThemedDialogHelper.Builder(this)",
        "ThemedDialogHelper.StyleShown(dialog, this)",
        "Background = Solid(Surface)",
    ]
    missing = [marker for marker in required if marker not in text]
    if missing:
        raise RuntimeError(f"MCSV inline API-key help patch incomplete: {missing}")

    forbidden = [
        "ดูวิธีเอา API Key",
        "HOW TO GET API KEY",
        "ShowMcsvApiKeyGuide",
        "McsvGuideStep",
        "ShowMcsvGuideImage",
        "Resource.Drawable.mcsv_api_key_guide",
        "Resource.Drawable.mcsv_api_step1",
        "Resource.Drawable.mcsv_api_step2",
        "Resource.Drawable.mcsv_api_step3",
    ]
    present = [marker for marker in forbidden if marker in text]
    if present:
        raise RuntimeError(f"Removed MCSV guide UI is still referenced: {present}")

    print(f"Applied MCSV inline API-key instructions + theme fix to {activity}")
    print(f"Theme-normalized {replacements} raw AlertDialog builder(s)")


if __name__ == "__main__":
    main()
