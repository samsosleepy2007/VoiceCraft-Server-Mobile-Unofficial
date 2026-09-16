#!/usr/bin/env python3
from pathlib import Path
import re
import shutil
import sys


def sub_required(text: str, pattern: str, replacement: str, label: str) -> str:
    updated, count = re.subn(pattern, replacement, text, count=1, flags=re.S)
    if count != 1:
        raise RuntimeError(f"MCSV theme/guide patch anchor missing: {label}")
    return updated


def copy_runtime_assets(repo: Path) -> None:
    src_root = repo / "VoiceCraft.Guest.Patch/VoiceCraft.Server.Android"
    dst_root = repo / "VoiceCraft.Server.Android"
    for rel in [
        "ThemedDialogHelper.cs",
        "Resources/drawable/mcsv_api_step1.webp",
        "Resources/drawable/mcsv_api_step2.webp",
        "Resources/drawable/mcsv_api_step3.webp",
    ]:
        src = src_root / rel
        dst = dst_root / rel
        if not src.exists():
            raise RuntimeError(f"MCSV theme/guide asset missing: {src}")
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

    guide_methods = r'''    private LinearLayout McsvGuideStep(string title, string detail, int imageResource, int imageHeightDp)
    {
        var card = new LinearLayout(this)
        {
            Orientation = Orientation.Vertical,
            Background = Round(SurfaceSoft, 18, Border)
        };
        card.SetPadding(Dp(12), Dp(12), Dp(12), Dp(12));
        card.AddView(Label(title, 15, Ink, true));
        var description = Label(detail, 11, Muted);
        description.SetPadding(0, Dp(4), 0, Dp(10));
        card.AddView(description);

        var image = new ImageView(this);
        image.SetImageResource(imageResource);
        image.SetScaleType(ImageView.ScaleType.FitCenter);
        image.SetAdjustViewBounds(false);
        image.SetBackgroundColor(_dark ? Color.Rgb(12, 18, 32) : Color.Rgb(242, 245, 250));
        image.ContentDescription = title;
        image.Clickable = true;
        image.Click += (_, _) => ShowMcsvGuideImage(imageResource, title);
        card.AddView(image, new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MatchParent, Dp(imageHeightDp)));

        var hint = Label(T("แตะภาพเพื่อดูขนาดใหญ่", "Tap the image to view larger"), 10, Muted);
        hint.Gravity = GravityFlags.CenterHorizontal;
        hint.SetPadding(0, Dp(7), 0, 0);
        card.AddView(hint);
        return card;
    }

    private void ShowMcsvGuideImage(int imageResource, string title)
    {
        var panel = new LinearLayout(this)
        {
            Orientation = Orientation.Vertical,
            Background = Solid(Surface)
        };
        panel.SetPadding(Dp(12), Dp(12), Dp(12), Dp(12));
        panel.AddView(Label(title, 16, Ink, true));

        var image = new ImageView(this);
        image.SetImageResource(imageResource);
        image.SetAdjustViewBounds(true);
        image.SetScaleType(ImageView.ScaleType.FitCenter);
        image.SetBackgroundColor(_dark ? Color.Rgb(12, 18, 32) : Color.Rgb(242, 245, 250));
        panel.AddView(image, new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MatchParent, 0, 1f) { TopMargin = Dp(10) });

        var dialog = ThemedDialogHelper.Builder(this)
            .SetView(panel)
            .SetPositiveButton(T("ปิด", "CLOSE"), (_, _) => { })
            .Create();
        dialog.Show();
        ThemedDialogHelper.StyleShown(dialog, this);
        var metrics = Resources?.DisplayMetrics;
        if (metrics != null)
            dialog.Window?.SetLayout((int)(metrics.WidthPixels * 0.94f), (int)(metrics.HeightPixels * 0.82f));
    }

    private void ShowMcsvApiKeyGuide()
    {
        var content = new LinearLayout(this)
        {
            Orientation = Orientation.Vertical,
            Background = Solid(Surface)
        };
        content.SetPadding(Dp(16), Dp(14), Dp(16), Dp(20));
        content.AddView(Label(T("วิธีเอา MCSV API Key", "How to get an MCSV API Key"), 19, Ink, true));
        var intro = Label(
            T("ทำตาม 3 ขั้นตอนนี้ แล้วนำ token ที่ขึ้นต้นด้วย mcsv_ กลับมาใส่ใน VoiceCraft", "Follow these 3 steps, then paste the mcsv_ token back into VoiceCraft."),
            12,
            Muted);
        intro.SetPadding(0, Dp(5), 0, Dp(12));
        content.AddView(intro);

        content.AddView(McsvGuideStep(
            T("1. เปิด API / MCP", "1. Open API / MCP"),
            T("เข้า MCSV แล้วเลือกเมนู API / MCP จากแถบซ้าย จากนั้นกด “สร้าง key”", "Open MCSV, choose API / MCP in the left menu, then tap Create key."),
            Resource.Drawable.mcsv_api_step1,
            174));

        var step2 = McsvGuideStep(
            T("2. สร้าง Key สำหรับ VoiceCraft", "2. Create a VoiceCraft key"),
            T("ตั้งชื่อ เช่น VoiceCraft → เลือก “สิทธิ์เต็ม” → กด “สร้าง key”", "Name it VoiceCraft → choose Full access → tap Create key."),
            Resource.Drawable.mcsv_api_step2,
            220);
        content.AddView(step2, new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MatchParent, ViewGroup.LayoutParams.WrapContent) { TopMargin = Dp(12) });

        var step3 = McsvGuideStep(
            T("3. Copy Token", "3. Copy the token"),
            T("กด Copy token ที่ขึ้นต้นด้วย mcsv_ แล้วกลับมาวางใน VoiceCraft Server Mobile", "Copy the token beginning with mcsv_, then paste it into VoiceCraft Server Mobile."),
            Resource.Drawable.mcsv_api_step3,
            220);
        content.AddView(step3, new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MatchParent, ViewGroup.LayoutParams.WrapContent) { TopMargin = Dp(12) });

        var warning = new LinearLayout(this)
        {
            Orientation = Orientation.Vertical,
            Background = Round(WarningFill, 16, Amber)
        };
        warning.SetPadding(Dp(12), Dp(10), Dp(12), Dp(10));
        warning.AddView(Label(
            T("MCSV จะแสดง token เพียงครั้งเดียว คัดลอกเก็บไว้ทันทีและอย่าส่งให้ผู้อื่น", "MCSV shows the token only once. Save it immediately and never share it."),
            11,
            Ink,
            true));
        content.AddView(warning, new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MatchParent, ViewGroup.LayoutParams.WrapContent) { TopMargin = Dp(14) });

        var scroll = new ScrollView(this)
        {
            FillViewport = true,
            Background = Solid(Surface)
        };
        scroll.AddView(content);

        var dialog = ThemedDialogHelper.Builder(this)
            .SetView(scroll)
            .SetPositiveButton(T("ปิด", "CLOSE"), (_, _) => { })
            .Create();
        dialog.Show();
        ThemedDialogHelper.StyleShown(dialog, this);
        var metrics = Resources?.DisplayMetrics;
        if (metrics != null)
            dialog.Window?.SetLayout((int)(metrics.WidthPixels * 0.94f), (int)(metrics.HeightPixels * 0.88f));
    }

    private void ShowMcsvSetup()'''

    text = sub_required(
        text,
        r"    private void ShowMcsvApiKeyGuide\(\)\n    \{.*?\n    \}\n\n    private void ShowMcsvSetup\(\)",
        guide_methods,
        "replace oversized guide",
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
                "วาง API Key ของเซิร์ฟเวอร์ MCSV (ขึ้นต้นด้วย mcsv_) ระบบจะตรวจสิทธิ์ ติดตั้ง Plugin + Addon แล้ว Restart เซิร์ฟเวอร์อัตโนมัติ",
                "Paste this MCSV server's API key (mcsv_…). VoiceCraft checks permissions, installs the plugin + add-on, then restarts the server automatically."),
            12,
            Ink);
        setupDescription.SetPadding(0, Dp(8), 0, Dp(6));
        panel.AddView(setupDescription);
        panel.AddView(InputLabel("MCSV API Key"));
        var apiKeyInput = Input(hasSaved ? savedToken : string.Empty, InputTypes.ClassText | InputTypes.TextVariationPassword);
        apiKeyInput.Hint = "mcsv_...";
        panel.AddView(apiKeyInput);
        panel.AddView(Label(
            T("ต้องอนุญาต File read/write, download/decompress/rename/delete และ Power restart", "The key needs file read/write, fetch/decompress/rename/delete and Power restart permissions."),
            10,
            Muted));

        var keyGuideButton = MakeButton(T("ดูวิธีเอา API Key", "HOW TO GET API KEY"));
        WireButton(keyGuideButton, ShowMcsvApiKeyGuide);
        panel.AddView(keyGuideButton, new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MatchParent, Dp(46)) { TopMargin = Dp(10) });

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
        "theme MCSV setup dialog",
    )

    activity.write_text(text, encoding="utf-8")
    replacements = theme_all_android_dialogs(repo)
    text = activity.read_text(encoding="utf-8")

    required = [
        "Resource.Drawable.mcsv_api_step1",
        "Resource.Drawable.mcsv_api_step2",
        "Resource.Drawable.mcsv_api_step3",
        "McsvGuideStep",
        "174));",
        "220);",
        "ThemedDialogHelper.Builder(this)",
        "ThemedDialogHelper.StyleShown(dialog, this)",
        "Background = Solid(Surface)",
        "แตะภาพเพื่อดูขนาดใหญ่",
    ]
    missing = [marker for marker in required if marker not in text]
    if missing:
        raise RuntimeError(f"MCSV theme/guide patch incomplete: {missing}")
    if "Resource.Drawable.mcsv_api_key_guide" in text:
        raise RuntimeError("Old oversized MCSV guide image is still referenced")

    print(f"Applied MCSV compact guide + theme fix to {activity}")
    print(f"Theme-normalized {replacements} raw AlertDialog builder(s)")


if __name__ == "__main__":
    main()
