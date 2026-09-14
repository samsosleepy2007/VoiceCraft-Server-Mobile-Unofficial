#!/usr/bin/env python3
from pathlib import Path
import sys


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise RuntimeError(f"MCSV integration patch anchor missing: {label}")
    return text.replace(old, new, 1)


def main() -> None:
    repo = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
    activity = repo / "VoiceCraft.Server.Android/ModernMainActivity.cs"
    if not activity.exists():
        raise SystemExit(f"ModernMainActivity.cs not found: {activity}")

    text = activity.read_text(encoding="utf-8")

    text = replace_once(
        text,
        "    private TextView? _configPreview;\n",
        "    private TextView? _configPreview;\n"
        "    private LinearLayout? _mcsvCard;\n"
        "    private TextView? _mcsvStatus;\n"
        "    private Button? _mcsvAction;\n"
        "    private bool _mcsvBusy;\n",
        "MCSV fields",
    )

    card = r'''        body.AddView(endstone, CardLayout());

        _mcsvCard = Card(SuccessFill, Green);
        _mcsvCard.Background = Round(SuccessFill, 22, Green, 2);
        _mcsvCard.Elevation = Dp(8);
        _mcsvCard.SetPadding(Dp(18), Dp(16), Dp(18), Dp(18));

        var mcsvHeader = new LinearLayout(this) { Orientation = Orientation.Horizontal };
        mcsvHeader.SetGravity(GravityFlags.CenterVertical);
        var mcsvLogo = new ImageView(this);
        mcsvLogo.SetImageResource(Resource.Drawable.mcsv_logo);
        mcsvLogo.SetAdjustViewBounds(true);
        mcsvLogo.SetScaleType(ImageView.ScaleType.FitCenter);
        mcsvHeader.AddView(mcsvLogo, new LinearLayout.LayoutParams(Dp(118), Dp(48)));

        var mcsvTitle = new LinearLayout(this) { Orientation = Orientation.Vertical };
        mcsvTitle.SetPadding(Dp(12), 0, 0, 0);
        mcsvTitle.AddView(Label(T("ใช้ MCSV อยู่รึป่าว?", "Using MCSV?"), 17, Ink, true));
        mcsvTitle.AddView(Label(T("ติดตั้ง VoiceCraft ให้เซิร์ฟเวอร์อัตโนมัติ", "Install VoiceCraft automatically"), 11, Green, true));
        mcsvHeader.AddView(mcsvTitle, new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WrapContent, 1f));
        _mcsvCard.AddView(mcsvHeader);

        var mcsvDescription = Label(
            T(
                "ใส่ MCSV API Key แล้วแอปจะติดตั้ง VoiceCraft Addon และ Endstone Plugin ให้อัตโนมัติ เขียน Relay Config ให้ครบ และ Restart เซิร์ฟเวอร์หลังติดตั้งเสร็จ",
                "Enter an MCSV API key and the app installs the VoiceCraft add-on and Endstone plugin, writes the Relay config, then restarts the server automatically."),
            12,
            Ink);
        mcsvDescription.SetPadding(0, Dp(12), 0, Dp(6));
        _mcsvCard.AddView(mcsvDescription);

        _mcsvCard.AddView(Label(
            T("API Key ถูกเก็บแบบเข้ารหัสด้วย Android Keystore และส่งเฉพาะไปยัง api.mcsv.me", "The API key is encrypted with Android Keystore and sent only to api.mcsv.me."),
            10,
            Muted));

        _mcsvStatus = Label(string.Empty, 12, Green, true);
        _mcsvStatus.SetPadding(0, Dp(12), 0, Dp(8));
        _mcsvCard.AddView(_mcsvStatus);

        _mcsvAction = MakeButton(T("เชื่อม API และติดตั้ง", "CONNECT & INSTALL"), primary: true);
        WireButton(_mcsvAction, ShowMcsvSetup);
        _mcsvCard.AddView(_mcsvAction, new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MatchParent, Dp(50)));
        _mcsvCard.Visibility = ViewStates.Gone;
        body.AddView(_mcsvCard, CardLayout());
        return scroll;'''

    text = replace_once(
        text,
        "        body.AddView(endstone, CardLayout());\n        return scroll;",
        card,
        "MCSV card directly below final Endstone integration",
    )

    text = replace_once(
        text,
        "        ApplyValidationHighlights();\n    }\n\n    private void ApplyValidationHighlights()",
        "        ApplyValidationHighlights();\n"
        "        RefreshMcsvCardVisibility(ready);\n"
        "    }\n\n"
        "    private void ApplyValidationHighlights()",
        "MCSV visibility refresh",
    )

    methods = r'''    private void RefreshMcsvCardVisibility(bool bridgeReady)
    {
        if (_mcsvCard == null)
            return;

        _mcsvCard.Visibility = bridgeReady ? ViewStates.Visible : ViewStates.Gone;
        if (!bridgeReady)
            return;

        var hasToken = McsvTokenStore.TryLoad(this, out _);
        if (_mcsvStatus != null && !_mcsvBusy)
        {
            _mcsvStatus.Text = hasToken
                ? T("● MCSV API เชื่อมไว้แล้ว — พร้อมติดตั้งหรืออัปเดต", "● MCSV API saved — ready to install or update")
                : T("● พร้อมเชื่อม MCSV API", "● Ready to connect MCSV API");
            _mcsvStatus.SetTextColor(Green);
        }
        if (_mcsvAction != null && !_mcsvBusy)
            _mcsvAction.Text = hasToken
                ? T("ติดตั้ง / อัปเดต VoiceCraft", "INSTALL / UPDATE VOICECRAFT")
                : T("เชื่อม API และติดตั้ง", "CONNECT & INSTALL");
    }

    private void ShowMcsvSetup()
    {
        if (_mcsvBusy)
            return;
        if (!ValidateBridge(CurrentWebSocket(), CurrentServerId(), CurrentSecret(), out _))
        {
            Toast.MakeText(this, T("ตั้งค่า Render Relay, Server ID และ Secret ให้ครบก่อน", "Complete Render Relay, Server ID and Secret first"), ToastLength.Long)?.Show();
            return;
        }

        var hasSaved = McsvTokenStore.TryLoad(this, out var savedToken);
        var panel = new LinearLayout(this) { Orientation = Orientation.Vertical };
        panel.SetPadding(Dp(22), Dp(4), Dp(22), 0);
        panel.AddView(Label(
            T(
                "วาง API Key ของเซิร์ฟเวอร์ MCSV (ขึ้นต้นด้วย mcsv_) ระบบจะตรวจสิทธิ์ ติดตั้ง Plugin + Addon แล้ว Restart เซิร์ฟเวอร์อัตโนมัติ",
                "Paste this MCSV server's API key (mcsv_…). VoiceCraft checks permissions, installs the plugin + add-on, then restarts the server automatically."),
            12,
            Ink));
        panel.AddView(InputLabel("MCSV API Key"));
        var apiKeyInput = Input(hasSaved ? savedToken : string.Empty, InputTypes.ClassText | InputTypes.TextVariationPassword);
        apiKeyInput.Hint = "mcsv_...";
        panel.AddView(apiKeyInput);
        panel.AddView(Label(
            T("ต้องอนุญาต File read/write, download/decompress/rename/delete และ Power restart", "The key needs file read/write, fetch/decompress/rename/delete and Power restart permissions."),
            10,
            Muted));

        var builder = new AlertDialog.Builder(this)
            .SetTitle(T("เชื่อม MCSV และติดตั้ง VoiceCraft", "Connect MCSV & Install VoiceCraft"))
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
        builder.Show();
    }

    private async Task RunMcsvInstallAsync(string apiKey)
    {
        if (_mcsvBusy)
            return;
        if (!apiKey.StartsWith("mcsv_", StringComparison.Ordinal))
        {
            Toast.MakeText(this, T("MCSV API Key ต้องขึ้นต้นด้วย mcsv_", "MCSV API key must start with mcsv_"), ToastLength.Long)?.Show();
            return;
        }

        _mcsvBusy = true;
        if (_mcsvAction != null)
            _mcsvAction.Enabled = false;
        SetMcsvStatus(T("กำลังตรวจสอบ MCSV API…", "Checking MCSV API…"), Green);

        try
        {
            using (var preflight = new McsvApiClient(apiKey))
                await preflight.ValidateKeyAsync();
            McsvTokenStore.Save(this, apiKey);
            SaveCurrentConfiguration();

            var result = await McsvVoiceCraftInstaller.InstallAsync(
                apiKey,
                CurrentWebSocket(),
                ServerPreferences.GetBridgeBackupUrls(this),
                CurrentServerId(),
                CurrentSecret(),
                status => RunOnUiThread(() => SetMcsvStatus(status, Green)));

            var restartText = result.ServerRunning
                ? T("เซิร์ฟเวอร์กลับมา Online แล้ว", "The server is back online")
                : T("ส่งคำสั่ง Restart แล้ว หากเซิร์ฟเวอร์ยังเริ่มอยู่ให้รอสักครู่", "Restart was requested; wait a moment if the server is still starting");
            var warning = string.IsNullOrWhiteSpace(result.Warning) ? string.Empty : "\n\n" + result.Warning;
            SetMcsvStatus(T("● ติดตั้งสำเร็จ", "● Installation complete"), Green);
            new AlertDialog.Builder(this)
                .SetTitle(T("ติดตั้ง VoiceCraft สำเร็จ", "VoiceCraft installed"))
                .SetMessage($"{result.ServerName}\n{restartText}{warning}")
                .SetPositiveButton("OK", (_, _) => { })
                .Show();
        }
        catch (Exception ex)
        {
            var message = ex.Message ?? T("เกิดข้อผิดพลาดที่ไม่ทราบสาเหตุ", "Unknown error");
            if (message.Length > 600)
                message = message[..600];
            SetMcsvStatus(T("● ติดตั้งไม่สำเร็จ", "● Installation failed"), Red);
            AndroidRuntimeLog.Append("MCSV", $"Install failed: {message}");
            new AlertDialog.Builder(this)
                .SetTitle(T("MCSV ติดตั้งไม่สำเร็จ", "MCSV installation failed"))
                .SetMessage(message)
                .SetPositiveButton("OK", (_, _) => { })
                .Show();
        }
        finally
        {
            _mcsvBusy = false;
            if (_mcsvAction != null)
                _mcsvAction.Enabled = true;
            RefreshMcsvCardVisibility(ValidateBridge(CurrentWebSocket(), CurrentServerId(), CurrentSecret(), out _));
        }
    }

    private void SetMcsvStatus(string text, Color color)
    {
        if (_mcsvStatus == null)
            return;
        _mcsvStatus.Text = text;
        _mcsvStatus.SetTextColor(color);
    }

'''

    marker = "    private void ShowInformation()"
    if marker not in text:
        raise RuntimeError("MCSV integration patch anchor missing: ShowInformation")
    text = text.replace(marker, methods + marker, 1)

    required = [
        "ใช้ MCSV อยู่รึป่าว?",
        "Resource.Drawable.mcsv_logo",
        "RefreshMcsvCardVisibility(ready)",
        "McsvVoiceCraftInstaller.InstallAsync",
        "McsvTokenStore.Save(this, apiKey)",
        "Restart เซิร์ฟเวอร์",
        "CONNECT & INSTALL",
        "body.AddView(endstone, CardLayout());",
    ]
    missing = [value for value in required if value not in text]
    if missing:
        raise RuntimeError(f"MCSV integration patch incomplete: {missing}")

    activity.write_text(text, encoding="utf-8")
    print(f"Applied MCSV Integration V1 UI patch: {activity}")


if __name__ == "__main__":
    main()
