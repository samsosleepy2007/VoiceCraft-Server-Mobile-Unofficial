#!/usr/bin/env python3
from pathlib import Path
import re
import sys


def sub_required(text: str, pattern: str, replacement: str, label: str) -> str:
    changed, count = re.subn(pattern, replacement, text, count=1, flags=re.S)
    if count != 1:
        raise RuntimeError(f"UI5 patch failed: {label} ({count})")
    return changed


def main() -> None:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
    path = root / "VoiceCraft.Server.Android" / "ModernMainActivity.cs"
    text = path.read_text(encoding="utf-8")

    # Figma baseline palette: icy light background, white cards, blue accent,
    # navy dark theme, green success and amber failover warning.
    text = text.replace("private static readonly Color Primary = Color.Rgb(73, 116, 255);", "private static readonly Color Primary = Color.Rgb(52, 139, 235);")
    text = text.replace("private static readonly Color Primary2 = Color.Rgb(105, 86, 255);", "private static readonly Color Primary2 = Color.Rgb(70, 155, 245);")
    text = text.replace("private static readonly Color Sky = Color.Rgb(89, 200, 250);", "private static readonly Color Sky = Color.Rgb(73, 166, 245);")
    text = text.replace("private Color Page => _dark ? Color.Rgb(12, 18, 32) : Color.Rgb(247, 248, 255);", "private Color Page => _dark ? Color.Rgb(7, 17, 31) : Color.Rgb(243, 247, 253);")
    text = text.replace("private Color Surface => _dark ? Color.Rgb(22, 30, 48) : Color.White;", "private Color Surface => _dark ? Color.Rgb(17, 29, 46) : Color.White;")
    text = text.replace("private Color SurfaceSoft => _dark ? Color.Rgb(28, 38, 60) : Color.Rgb(248, 250, 255);", "private Color SurfaceSoft => _dark ? Color.Rgb(20, 34, 54) : Color.Rgb(244, 248, 253);")
    text = text.replace("private Color Tint => _dark ? Color.Rgb(35, 48, 82) : Color.Rgb(237, 242, 255);", "private Color Tint => _dark ? Color.Rgb(19, 42, 73) : Color.Rgb(230, 241, 253);")
    text = text.replace("private Color Ink => _dark ? Color.Rgb(246, 248, 255) : Color.Rgb(35, 39, 54);", "private Color Ink => _dark ? Color.Rgb(244, 248, 255) : Color.Rgb(20, 35, 54);")
    text = text.replace("private Color Muted => _dark ? Color.Rgb(160, 170, 190) : Color.Rgb(116, 124, 145);", "private Color Muted => _dark ? Color.Rgb(151, 169, 191) : Color.Rgb(112, 128, 145);")
    text = text.replace("private Color Border => _dark ? Color.Rgb(51, 63, 87) : Color.Rgb(228, 232, 244);", "private Color Border => _dark ? Color.Rgb(31, 48, 71) : Color.Rgb(225, 233, 243);")

    # Header is now part of each page, matching the supplied Figma frames.
    text = text.replace("shell.AddView(BuildHeader(), new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MatchParent, Dp(88)));", "shell.AddView(BuildHeader(), new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MatchParent, Dp(0)));")

    header = '''    private View BuildHeader()
    {
        return new Space(this) { Visibility = ViewStates.Gone };
    }

'''
    text = sub_required(text, r"    private View BuildHeader\(\)\n    \{.*?\n    \}\n\n(?=    private View BuildNav\(\))", header, "header")

    nav = '''    private View BuildNav()
    {
        var outer = new LinearLayout(this)
        {
            Orientation = Orientation.Vertical,
            Background = Solid(Page)
        };
        outer.SetPadding(Dp(14), Dp(4), Dp(14), Dp(12));

        var bar = new LinearLayout(this)
        {
            Orientation = Orientation.Horizontal,
            Background = Round(Surface, 26, Border)
        };
        bar.Elevation = Dp(5);
        bar.SetGravity(GravityFlags.Center);
        bar.SetPadding(Dp(5), Dp(5), Dp(5), Dp(5));

        AddNav(bar, T("หน้าหลัก", "Home"), 0);
        AddNav(bar, T("เซิร์ฟเวอร์", "Server"), 1);

        _navPower = MakeButton("▶", primary: true, compact: true);
        _navPower.TextSize = 21;
        WireButton(_navPower, () =>
        {
            if (VcServerApp.IsRunning || VoiceCraftServerService.IsServiceRunning)
                StopServer();
            else
                StartServer();
        });
        _navPower.Elevation = Dp(7);
        _navPower.Background = Round(Primary, 30, _dark ? Color.Rgb(36, 78, 125) : Color.Rgb(202, 225, 250), 5);
        bar.AddView(_navPower, new LinearLayout.LayoutParams(0, Dp(62), 1.15f)
        {
            LeftMargin = Dp(5),
            RightMargin = Dp(5)
        });

        AddNav(bar, T("บันทึก", "Logs"), 2);
        AddNav(bar, T("ตั้งค่า", "Settings"), 3);
        outer.AddView(bar, new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MatchParent, Dp(72)));
        return outer;
    }

'''
    text = sub_required(text, r"    private View BuildNav\(\)\n    \{.*?\n    \}\n\n(?=    private void AddNav)", nav, "bottom navigation")

    home = '''    private ScrollView BuildHome()
    {
        var (scroll, body) = NewPage(
            T("แดชบอร์ดเซิร์ฟเวอร์", "Server Dashboard"),
            T("โฮสต์เสียงระยะใกล้จากอุปกรณ์เครื่องนี้โดยตรง", "Host proximity voice directly from this device"));

        var onlineRow = new LinearLayout(this) { Orientation = Orientation.Horizontal };
        onlineRow.SetGravity(GravityFlags.CenterVertical);
        _statusBadge = Pill(T("● ออฟไลน์", "● OFFLINE"), _dark ? Color.Rgb(20, 58, 48) : Color.Rgb(229, 249, 239), Green, true);
        onlineRow.AddView(_statusBadge, new LinearLayout.LayoutParams(ViewGroup.LayoutParams.WrapContent, Dp(32)));
        body.AddView(onlineRow, Top(Dp(2)));

        body.AddView(Label("VoiceCraft Server", 18, Ink, true), Top(Dp(12)));
        _address = Label(T("กำลังค้นหา LAN IP…", "Detecting LAN address…"), 12, Muted);
        _address.SetTextIsSelectable(true);
        body.AddView(_address, Top(Dp(4)));

        var running = Card();
        var runningRow = new LinearLayout(this) { Orientation = Orientation.Horizontal };
        runningRow.SetGravity(GravityFlags.CenterVertical);
        var vc = Pill("VC", _dark ? Color.Rgb(18, 55, 96) : Color.Rgb(231, 242, 254), Primary, true);
        vc.TextSize = 13;
        runningRow.AddView(vc, new LinearLayout.LayoutParams(Dp(54), Dp(54)) { RightMargin = Dp(14) });
        var runningText = new LinearLayout(this) { Orientation = Orientation.Vertical };
        _statusTitle = Label(T("เซิร์ฟเวอร์หยุดอยู่", "Server is stopped"), 15, Ink, true);
        _statusDetail = Label(T("พร้อมเริ่มเมื่อการตั้งค่าครบ", "Ready when setup is complete"), 11, Muted);
        runningText.AddView(_statusTitle);
        runningText.AddView(_statusDetail, Top(Dp(4)));
        _clientCount = Label("0", 11, Muted);
        runningText.AddView(_clientCount, Top(Dp(6)));
        runningRow.AddView(runningText, new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WrapContent, 1f));
        running.AddView(runningRow);
        var progress = new ProgressBar(this, null, global::Android.Resource.Attribute.ProgressBarStyleHorizontal)
        {
            Indeterminate = false,
            Progress = 72,
            Max = 100
        };
        running.AddView(progress, new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MatchParent, Dp(5)) { TopMargin = Dp(12) });
        body.AddView(running, CardLayout());

        var metrics1 = new LinearLayout(this) { Orientation = Orientation.Horizontal };
        metrics1.AddView(MetricCard("0", "Voice Clients", out _clientCount), Weight());
        metrics1.AddView(MetricCard("0", "Minecraft", out _minecraftCount), Weight());
        body.AddView(metrics1, CardLayout());

        var metrics2 = new LinearLayout(this) { Orientation = Orientation.Horizontal };
        metrics2.AddView(MetricCard("0", T("เชื่อม Voice", "Bound"), out _boundCount), Weight());
        metrics2.AddView(MetricCard(T("หลัก", "Primary"), "Relay", out _bridgeState), Weight());
        body.AddView(metrics2, CardLayout());

        _errorCard = Card(WarningFill, Amber);
        _errorCard.Visibility = ViewStates.Gone;
        _errorText = Label(string.Empty, 12, Ink);
        _errorCard.AddView(_errorText);
        var errorButtons = ButtonRow();
        AddButton(errorButtons, T("เปิด Logs", "OPEN LOGS"), () => ShowPage(2), primary: true);
        AddButton(errorButtons, T("ตั้งค่า Server", "SERVER SETUP"), () => ShowPage(1));
        _errorCard.AddView(errorButtons);
        body.AddView(_errorCard, CardLayout());

        var connection = Card();
        connection.AddView(SectionTitle(T("การเชื่อมต่อ", "Connection"), Primary));
        _relaySummary = Label(T("ยังไม่ได้ตั้งค่า Relay", "Relay not configured"), 12, Ink, true);
        _relaySummary.SetTextIsSelectable(true);
        connection.AddView(_relaySummary);
        var actions = ButtonRow();
        AddButton(actions, T("ขอ Snapshot", "SNAPSHOT"), () =>
        {
            var queued = VoiceCraftServerService.RequestBridgeSnapshot();
            Toast.MakeText(this, queued ? T("ขอ Snapshot แล้ว", "Snapshot requested") : T("Bridge ยังไม่ทำงาน", "Bridge is not running"), ToastLength.Short)?.Show();
        }, primary: true);
        AddButton(actions, T("คัดลอก IP:Port", "COPY IP:PORT"), CopyAddress);
        connection.AddView(actions);
        body.AddView(connection, CardLayout());

        var players = Card();
        players.AddView(SectionTitle(T("ผู้เล่นและ Bind", "Players & Binding"), Primary));
        _playerList = Label(T("ยังไม่มีผู้เล่น Minecraft ที่ติดตาม", "No tracked Minecraft players yet"), 11, Muted);
        _playerList.SetTextIsSelectable(true);
        players.AddView(_playerList);
        body.AddView(players, CardLayout());
        return scroll;
    }

'''
    text = sub_required(text, r"    private ScrollView BuildHome\(\)\n    \{.*?\n    \}\n\n(?=    private ScrollView BuildBridge\(\))", home, "dashboard")

    setup = '''    private ScrollView BuildBridge()
    {
        var (scroll, body) = NewPage(
            T("ตั้งค่าเซิร์ฟเวอร์", "Server Setup"),
            T("ตั้งค่า VoiceCraft, Render Relay และ Endstone", "Configure VoiceCraft, Render Relay and Endstone"));
        _bridgeScroll = scroll;

        _readiness = Pill(T("● ต้องตั้งค่า", "● SETUP REQUIRED"), WarningFill, Amber, true);
        body.AddView(_readiness, new LinearLayout.LayoutParams(ViewGroup.LayoutParams.WrapContent, Dp(32)) { BottomMargin = Dp(12) });

        var voice = Card();
        voice.AddView(SectionTitle(T("เซิร์ฟเวอร์เสียง", "Voice Server"), Primary));
        voice.AddView(InputLabel("Port"));
        _port = Input(ServerPreferences.GetVoicePort(this).ToString(), InputTypes.ClassNumber);
        _port.TextChanged += (_, _) => ApplyValidationHighlights();
        voice.AddView(_port);
        voice.AddView(InputLabel(T("Server Key", "Server Key")));
        _serverKey = Input(ServerPreferences.GetServerKey(this), InputTypes.ClassText | InputTypes.TextVariationPassword);
        voice.AddView(_serverKey);
        var keyButtons = ButtonRow();
        AddButton(keyButtons, T("แสดง/ซ่อน", "SHOW / HIDE"), ToggleServerKey);
        AddButton(keyButtons, T("สร้าง Key", "GENERATE"), GenerateServerKey);
        voice.AddView(keyButtons);
        body.AddView(voice, CardLayout());

        var relay = Card();
        var relayHead = new LinearLayout(this) { Orientation = Orientation.Horizontal };
        relayHead.SetGravity(GravityFlags.CenterVertical);
        relayHead.AddView(SectionTitle("Render Relay", Primary), new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WrapContent, 1f));
        relayHead.AddView(Pill(T("● เชื่อมต่อ", "● CONNECTED"), SuccessFill, Green, true), new LinearLayout.LayoutParams(ViewGroup.LayoutParams.WrapContent, Dp(30)));
        relay.AddView(relayHead);
        _renderUrl = Input(ToServiceUrl(ServerPreferences.GetBridgeUrl(this)), InputTypes.ClassText | InputTypes.TextVariationUri);
        _renderUrl.Hint = "https://voicecraft-server.onrender.com";
        _renderUrl.TextChanged += (_, _) => UpdateWebSocketFromRenderUrl();
        relay.AddView(_renderUrl);
        _webSocketUrl = ReadOnly(T("ใส่ Render URL ด้านบน", "Enter Render URL above"));
        relay.AddView(_webSocketUrl, Top(Dp(10)));
        body.AddView(relay, CardLayout());

        var identity = Card();
        identity.AddView(SectionTitle(T("Server ID และ Secret", "Server ID & Secret"), Primary));
        identity.AddView(InputLabel("Server ID"));
        _serverId = Input(ServerPreferences.GetBridgeServerId(this), InputTypes.ClassText);
        _serverId.Hint = T("ใส่อะไรก็ได้ เช่น ชื่อโปรเจกต์", "Any value, for example your project name");
        _serverId.TextChanged += (_, _) => RefreshBridgePreview();
        identity.AddView(_serverId);
        identity.AddView(Label(T("ใช้ระบุเซิร์ฟเวอร์และชื่อไฟล์ Plugin ที่ดาวน์โหลด", "Used to identify the server and downloaded Plugin file"), 10, Muted), Top(Dp(4)));
        identity.AddView(InputLabel("Bridge Secret"));
        _bridgeSecret = Input(ServerPreferences.GetBridgeSecret(this), InputTypes.ClassText | InputTypes.TextVariationPassword);
        _bridgeSecret.TextChanged += (_, _) => RefreshBridgePreview();
        identity.AddView(_bridgeSecret);
        var secrets = ButtonRow();
        AddButton(secrets, T("แสดง/ซ่อน", "SHOW / HIDE"), ToggleBridgeSecret);
        AddButton(secrets, T("สร้าง", "GENERATE"), GenerateBridgeSecret);
        identity.AddView(secrets);
        var backup = ButtonRow();
        AddButton(backup, T("จัดการ Backup Relay", "MANAGE BACKUP RELAYS"), OpenBackupRelays, primary: true);
        identity.AddView(backup);
        identity.AddView(Label(T("Backup Relay ใช้ได้เฉพาะ Premium หรือ Admin", "Backup Relay is available to Premium or Admin accounts"), 10, Muted), Top(Dp(4)));
        body.AddView(identity, CardLayout());

        var endstone = Card();
        endstone.AddView(SectionTitle(T("Endstone Integration", "Endstone Integration"), Primary));
        endstone.AddView(Label(T("Plugin 0.2.7 • Item Mic เปิดใช้งาน", "Plugin 0.2.7 • Item Mic enabled"), 11, Muted));
        endstone.AddView(Label(T("● Minecraft bridge connected", "● Minecraft bridge connected"), 11, Green, true), Top(Dp(8)));
        _configPreview = Label(string.Empty, 10, Ink);
        _configPreview.Typeface = Typeface.Monospace;
        _configPreview.SetTextIsSelectable(true);
        _configPreview.SetPadding(Dp(10), Dp(10), Dp(10), Dp(10));
        _configPreview.Background = Round(SurfaceSoft, 14, Border);
        endstone.AddView(_configPreview, Top(Dp(10)));
        var configButtons = ButtonRow();
        AddButton(configButtons, T("คัดลอก Config", "COPY CONFIG"), CopyPluginConfig);
        AddButton(configButtons, T("คัดลอกข้อมูลตั้งค่าทั้งหมด", "COPY ALL SETUP"), CopyAllSetup, primary: true);
        endstone.AddView(configButtons);
        body.AddView(endstone, CardLayout());
        return scroll;
    }

'''
    text = sub_required(text, r"    private ScrollView BuildBridge\(\)\n    \{.*?\n    \}\n\n(?=    private ScrollView BuildLogs\(\))", setup, "server setup")

    logs = '''    private ScrollView BuildLogs()
    {
        var (scroll, body) = NewPage(
            T("บันทึกการทำงาน", "Runtime Logs"),
            T("ดูสถานะ Server, Bridge และระบบเสียงแบบสด", "Live server, bridge and voice diagnostics"));

        var filters = ButtonRow();
        AddButton(filters, "All", () => { _logFilter = "ALL"; RefreshLog(true); }, primary: _logFilter == "ALL");
        AddButton(filters, "Server", () => { _logFilter = "SERVER"; RefreshLog(true); }, primary: _logFilter == "SERVER");
        AddButton(filters, "Bridge", () => { _logFilter = "BRIDGE"; RefreshLog(true); }, primary: _logFilter == "BRIDGE");
        AddButton(filters, "Voice", () => { _logFilter = "VOICE"; RefreshLog(true); }, primary: _logFilter == "VOICE");
        body.AddView(filters, new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MatchParent, Dp(60)) { BottomMargin = Dp(6) });

        _logSearch = Input(string.Empty, InputTypes.ClassText);
        _logSearch.Hint = T("ค้นหา log...", "Search logs...");
        _logSearch.TextChanged += (_, _) => RefreshLog(true);
        body.AddView(_logSearch, new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MatchParent, Dp(48)) { BottomMargin = Dp(12) });

        var card = Card(_dark ? Color.Rgb(12, 24, 39) : Color.Rgb(14, 27, 44), _dark ? Color.Rgb(31, 50, 75) : Color.Rgb(14, 27, 44));
        card.AddView(Label("LIVE", 10, Green, true));
        _logView = Label(T("(ยังไม่มี Log)", "(no log entries yet)"), 10.5f, Color.Rgb(208, 220, 235));
        _logView.Typeface = Typeface.Monospace;
        _logView.SetMinHeight(Dp(300));
        _logView.SetTextIsSelectable(true);
        _logView.SetPadding(0, Dp(12), 0, 0);
        card.AddView(_logView);
        body.AddView(card, CardLayout());

        var buttons = ButtonRow();
        AddButton(buttons, T("คัดลอก Log", "COPY LOG"), CopyLog, primary: true);
        AddButton(buttons, T("ล้าง", "CLEAR"), () => { AndroidRuntimeLog.Clear(); RefreshLog(true); });
        AddButton(buttons, T("หยุดชั่วคราว", "PAUSE"), () => { _logPaused = !_logPaused; RefreshLog(true); });
        body.AddView(buttons, CardLayout());

        var health = Card(SuccessFill, Color.Transparent);
        health.AddView(Label(T("● ไม่พบปัญหา", "● No problems detected"), 12, Ink, true));
        _logHelp = Label(T("Secret และ binding key จะไม่ถูกแสดงใน logs", "Secrets and binding keys are hidden from logs"), 10, Muted);
        health.AddView(_logHelp, Top(Dp(4)));
        body.AddView(health, CardLayout());
        return scroll;
    }

'''
    text = sub_required(text, r"    private ScrollView BuildLogs\(\)\n    \{.*?\n    \}\n\n(?=    private ScrollView BuildSettings\(\))", logs, "runtime logs")

    settings = '''    private ScrollView BuildSettings()
    {
        var (scroll, body) = NewPage(
            T("ตั้งค่าแอป", "App Settings"),
            T("บัญชี รูปลักษณ์ การแจ้งเตือน และเครดิต", "Account, appearance, notifications and credits"));
        _settingsScroll = scroll;

        var account = Card();
        account.AddView(SectionTitle(T("ศูนย์บัญชี", "Account Center"), Primary));
        account.AddView(SettingsAction(
            T("บัญชี VoiceCraft", "VoiceCraft Account"),
            T("ดูบัญชีที่ใช้งาน สลับ Free Account หรือออกจากระบบ", "View the active account, switch Free Account, or log out"),
            T("จัดการ", "MANAGE"),
            OpenAccountCenter));
        body.AddView(account, CardLayout());

        var appearance = Card();
        appearance.AddView(SectionTitle(T("ภาษาและธีม", "Language & Theme"), Primary));
        appearance.AddView(SettingsAction(
            T("ภาษา", "Language"),
            T(_thai ? "ภาษาไทย" : "English", _thai ? "Thai" : "English"),
            _thai ? "ENGLISH" : "ไทย",
            ToggleLanguage));
        appearance.AddView(SettingsAction(
            T("ธีม", "Theme"),
            T(_dark ? "ธีมมืด" : "ธีมสว่าง", _dark ? "Dark theme" : "Light theme"),
            _dark ? T("สว่าง", "LIGHT") : T("มืด", "DARK"),
            ToggleTheme), Top(Dp(8)));
        body.AddView(appearance, CardLayout());

        var notifications = Card();
        notifications.AddView(SectionTitle(T("การแจ้งเตือน", "Notifications"), Primary));
        notifications.AddView(SettingsAction(
            T("สถานะเซิร์ฟเวอร์", "Server status"),
            T("จัดการการแจ้งเตือนสถานะ Relay และการหลุด", "Manage relay failover and disconnect alerts"),
            T("จัดการ", "MANAGE"),
            () =>
            {
                try
                {
                    var intent = new Intent(global::Android.Provider.Settings.ActionAppNotificationSettings);
                    intent.PutExtra(global::Android.Provider.Settings.ExtraAppPackage, PackageName);
                    StartActivity(intent);
                }
                catch { RequestNotificationPermission(); }
            }));
        body.AddView(notifications, CardLayout());

        var about = Card();
        about.AddView(SectionTitle(T("เกี่ยวกับ VoiceCraft Server", "About VoiceCraft Server"), Primary));
        about.AddView(Label(T("v1.7.1 • แนวคิด UI5 • รุ่นดัดแปลงแบบไม่เป็นทางการ", "v1.7.1 • UI5 concept • unofficial modified build"), 11, Muted));
        var aboutButtons = ButtonRow();
        AddButton(aboutButtons, T("ข้อมูล", "INFO"), ShowInformation);
        AddButton(aboutButtons, T("โอเพนซอร์ส", "OPEN SOURCE"), ShowOpenSourceLegal);
        AddButton(aboutButtons, T("เครดิต", "CREDITS"), ShowOpenSourceLegal, primary: true);
        about.AddView(aboutButtons);
        body.AddView(about, CardLayout());
        return scroll;
    }

'''
    text = sub_required(text, r"    private ScrollView BuildSettings\(\)\n    \{.*?\n    \}\n\n(?=    private \(ScrollView Scroll, LinearLayout Body\) NewPage)", settings, "app settings")

    newpage = '''    private (ScrollView Scroll, LinearLayout Body) NewPage(string title, string subtitle)
    {
        var scroll = new ScrollView(this) { FillViewport = true, Background = Solid(Page) };
        var body = new LinearLayout(this) { Orientation = Orientation.Vertical };
        body.SetPadding(Dp(20), Dp(22), Dp(20), Dp(34));

        var brand = Label("VOICECRAFT", 10, Primary, true);
        brand.LetterSpacing = 0.04f;
        body.AddView(brand);
        body.AddView(Label(title, 26, Ink, true), Top(Dp(10)));
        var sub = Label(subtitle, 11, Muted);
        sub.SetPadding(0, Dp(4), 0, Dp(18));
        body.AddView(sub);
        scroll.AddView(body);
        return (scroll, body);
    }

'''
    text = sub_required(text, r"    private \(ScrollView Scroll, LinearLayout Body\) NewPage\(string title, string subtitle\)\n    \{.*?\n    \}\n\n(?=    private LinearLayout Card)", newpage, "page heading")

    metric = '''    private LinearLayout MetricCard(string value, string caption, out TextView valueView)
    {
        var box = new LinearLayout(this)
        {
            Orientation = Orientation.Vertical,
            Background = Round(Surface, 18, Border)
        };
        box.SetPadding(Dp(14), Dp(12), Dp(14), Dp(12));
        valueView = Label(value, 19, Ink, true);
        var captionView = Label(caption, 10, Muted);
        box.AddView(captionView);
        box.AddView(valueView, Top(Dp(7)));
        return box;
    }

'''
    text = sub_required(text, r"    private LinearLayout MetricCard\(string value, string caption, out TextView valueView\)\n    \{.*?\n    \}\n\n(?=    private View FlowStep)", metric, "metric cards")

    text = text.replace("card.Background = gradient ? Gradient(Primary, Primary2, 24) : Round(fill ?? Surface, 22, stroke ?? Border);", "card.Background = gradient ? Gradient(Primary, Primary2, 22) : Round(fill ?? Surface, 20, stroke ?? Border);")
    text = text.replace("card.Elevation = Dp(2);", "card.Elevation = Dp(1);", 1)
    text = text.replace("private LinearLayout.LayoutParams CardLayout() => new(ViewGroup.LayoutParams.MatchParent, ViewGroup.LayoutParams.WrapContent) { BottomMargin = Dp(14) };", "private LinearLayout.LayoutParams CardLayout() => new(ViewGroup.LayoutParams.MatchParent, ViewGroup.LayoutParams.WrapContent) { BottomMargin = Dp(12) };")

    # Logs filtering / pause state.
    text = text.replace("    private TextView? _logHelp;\n", "    private TextView? _logHelp;\n    private EditText? _logSearch;\n    private string _logFilter = \"ALL\";\n    private bool _logPaused;\n")

    refresh_log = '''    private void RefreshLog(bool force = false)
    {
        if (_logView == null || _logPaused)
            return;
        var version = AndroidRuntimeLog.Version;
        if (!force && version == _renderedLogVersion)
            return;
        _renderedLogVersion = version;
        var text = AndroidRuntimeLog.Snapshot(_thai);
        if (!string.IsNullOrWhiteSpace(text))
        {
            var rows = text.Split('\\n');
            if (_logFilter != "ALL")
                rows = rows.Where(row => row.Contains(_logFilter, StringComparison.OrdinalIgnoreCase)).ToArray();
            var query = _logSearch?.Text?.Trim();
            if (!string.IsNullOrWhiteSpace(query))
                rows = rows.Where(row => row.Contains(query, StringComparison.OrdinalIgnoreCase)).ToArray();
            text = string.Join("\\n", rows);
        }
        _logView.Text = string.IsNullOrWhiteSpace(text) ? T("(ไม่พบ Log ที่ตรงเงื่อนไข)", "(no matching log entries)") : text;
    }

'''
    text = sub_required(text, r"    private void RefreshLog\(bool force = false\)\n    \{.*?\n    \}\n\n(?=    private void Pulse)", refresh_log, "log filtering")

    # Adapt live text to the Figma copy and neutral card colors.
    text = text.replace('                _statusTitle.Text = T("ผิดพลาด", "ERROR");', '                _statusTitle.Text = T("เซิร์ฟเวอร์มีปัญหา", "Server needs attention");')
    text = text.replace('                _statusTitle.Text = T("กำลังทำงาน", "RUNNING");', '                _statusTitle.Text = T("เซิร์ฟเวอร์กำลังทำงาน", "Server is running");')
    text = text.replace('                _statusTitle.Text = T("กำลังเริ่ม", "STARTING");', '                _statusTitle.Text = T("กำลังเริ่มเซิร์ฟเวอร์", "Server is starting");')
    text = text.replace('                _statusTitle.Text = T("หยุดอยู่", "STOPPED");', '                _statusTitle.Text = T("เซิร์ฟเวอร์หยุดอยู่", "Server is stopped");')
    text = text.replace("            _statusTitle.SetTextColor(Color.White);", "            _statusTitle.SetTextColor(Ink);")

    text = sub_required(
        text,
        r"        if \(_statusBadge != null\)\n        \{.*?\n        \}\n\n        if \(visualState != _lastVisualState\)",
        '''        if (_statusBadge != null)
        {
            var badge = visualState switch
            {
                "running" => (T("● ออนไลน์", "● ONLINE"), SuccessFill, Green),
                "starting" => (T("● กำลังเริ่ม", "● STARTING"), WarningFill, Amber),
                "error" => (T("● ผิดพลาด", "● ERROR"), DangerFill, Red),
                _ => (T("● ออฟไลน์", "● OFFLINE"), Tint, Muted)
            };
            _statusBadge.Text = badge.Item1;
            _statusBadge.SetTextColor(badge.Item3);
            _statusBadge.Background = Round(badge.Item2, 14);
        }

        if (visualState != _lastVisualState)''',
        "status badge")

    text = text.replace("        if (_bridgeState != null)\n            _bridgeState.Text = ShortBridge(VoiceCraftServerService.BridgeStatus);", '''        if (_bridgeState != null)
        {
            var relayIndex = VoiceCraftServerService.BridgeActiveRelayIndex;
            _bridgeState.Text = relayIndex > 0 ? $"Backup #{relayIndex}" : T("หลัก", "Primary");
        }''')
    text = text.replace('            _navPower.Text = active ? T("หยุด", "STOP") : T("เริ่ม", "START");', '            _navPower.Text = active ? "■" : "▶";')
    text = text.replace("            _navPower.Background = Round(active ? Red : Primary, 18, active ? Red : Primary);", "            _navPower.Background = Round(active ? Red : Primary, 30, _dark ? Color.Rgb(36, 78, 125) : Color.Rgb(202, 225, 250), 5);")

    # Port now belongs to Server Setup page rather than App Settings.
    text = text.replace('issues.Add(new ValidationIssue(T("Port ไม่ถูกต้อง", "Invalid port"), T("กรอกเลข 1–65535 ใน Settings", "Enter 1–65535 in Settings"), 3, _port));', 'issues.Add(new ValidationIssue(T("Port ไม่ถูกต้อง", "Invalid port"), T("กรอกเลข 1–65535 ใน Server Setup", "Enter 1–65535 in Server Setup"), 1, _port));')
    text = text.replace('        1 => T("หน้า Bridge Setup", "Bridge Setup"),', '        1 => T("หน้า Server Setup", "Server Setup"),')
    text = text.replace('        3 => T("หน้า Settings", "Settings"),', '        3 => T("หน้า App Settings", "App Settings"),')

    path.write_text(text, encoding="utf-8")

    final = path.read_text(encoding="utf-8")
    required = [
        'T("แดชบอร์ดเซิร์ฟเวอร์", "Server Dashboard")',
        'T("ตั้งค่าเซิร์ฟเวอร์", "Server Setup")',
        'T("บันทึกการทำงาน", "Runtime Logs")',
        'T("ตั้งค่าแอป", "App Settings")',
        'private string _logFilter = "ALL";',
        'Backup Relay is available to Premium or Admin accounts',
        'COPY ALL SETUP',
        'ShowOpenSourceLegal',
        'OpenAccountCenter',
    ]
    missing = [value for value in required if value not in final]
    if missing:
        raise RuntimeError(f"UI5 validation failed: {missing}")
    print(f"Applied UI5 Figma redesign to {path}")


if __name__ == "__main__":
    main()
