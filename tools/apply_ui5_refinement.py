#!/usr/bin/env python3
from pathlib import Path
import re
import sys


def sub_required(text: str, pattern: str, replacement: str, label: str) -> str:
    changed, count = re.subn(pattern, replacement, text, count=1, flags=re.S)
    if count != 1:
        raise RuntimeError(f"UI5 refinement failed: {label} ({count})")
    return changed


def main() -> None:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
    path = root / "VoiceCraft.Server.Android" / "ModernMainActivity.cs"
    text = path.read_text(encoding="utf-8")

    # Hide the legacy Voice Server card from Server Setup while keeping the
    # persisted/runtime port and server key fallbacks intact.
    text = sub_required(
        text,
        r"\n        var voice = Card\(\);.*?\n        body\.AddView\(voice, CardLayout\(\)\);\n",
        "\n",
        "remove legacy Voice Server setup card",
    )

    if "private TextView? _portAddress;" not in text:
        text = text.replace(
            "    private TextView? _address;\n",
            "    private TextView? _address;\n    private TextView? _portAddress;\n",
            1,
        )

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
        runningRow.AddView(runningText, new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WrapContent, 1f));
        running.AddView(runningRow);

        var addressBox = new LinearLayout(this)
        {
            Orientation = Orientation.Vertical,
            Background = Round(SurfaceSoft, 16, Border)
        };
        addressBox.SetPadding(Dp(14), Dp(12), Dp(14), Dp(12));
        addressBox.AddView(Label(T("ที่อยู่เซิร์ฟเวอร์", "SERVER ADDRESS"), 10, Primary, true));

        var ipRow = new LinearLayout(this) { Orientation = Orientation.Horizontal };
        ipRow.SetGravity(GravityFlags.CenterVertical);
        var ipText = new LinearLayout(this) { Orientation = Orientation.Vertical };
        ipText.AddView(Label("IP", 10, Muted, true));
        _address = Label(T("กำลังค้นหา LAN IP…", "Detecting LAN IP…"), 16, Ink, true);
        _address.SetTextIsSelectable(true);
        ipText.AddView(_address, Top(Dp(3)));
        ipRow.AddView(ipText, new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WrapContent, 1f));
        var copyIp = MakeButton(T("คัดลอก IP", "COPY IP"), primary: false, compact: true);
        WireButton(copyIp, CopyIp);
        ipRow.AddView(copyIp, new LinearLayout.LayoutParams(Dp(104), Dp(44)) { LeftMargin = Dp(10) });
        addressBox.AddView(ipRow, Top(Dp(9)));

        var portRow = new LinearLayout(this) { Orientation = Orientation.Horizontal };
        portRow.SetGravity(GravityFlags.CenterVertical);
        var portText = new LinearLayout(this) { Orientation = Orientation.Vertical };
        portText.AddView(Label("PORT", 10, Muted, true));
        _portAddress = Label(ServerPreferences.GetVoicePort(this).ToString(), 16, Ink, true);
        _portAddress.SetTextIsSelectable(true);
        portText.AddView(_portAddress, Top(Dp(3)));
        portRow.AddView(portText, new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WrapContent, 1f));
        var copyPort = MakeButton(T("คัดลอก Port", "COPY PORT"), primary: false, compact: true);
        WireButton(copyPort, CopyPort);
        portRow.AddView(copyPort, new LinearLayout.LayoutParams(Dp(104), Dp(44)) { LeftMargin = Dp(10) });
        addressBox.AddView(portRow, Top(Dp(9)));
        running.AddView(addressBox, Top(Dp(14)));

        var progress = new ProgressBar(this, null, global::Android.Resource.Attribute.ProgressBarStyleHorizontal)
        {
            Indeterminate = false,
            Progress = 72,
            Max = 100
        };
        running.AddView(progress, new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MatchParent, Dp(5)) { TopMargin = Dp(14) });
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
    text = sub_required(
        text,
        r"    private ScrollView BuildHome\(\)\n    \{.*?\n    \}\n\n(?=    private ScrollView BuildBridge\(\))",
        home,
        "dashboard address card",
    )

    logs = '''    private ScrollView BuildLogs()
    {
        var (scroll, body) = NewPage(
            T("บันทึกการทำงาน", "Runtime Logs"),
            T("ดูสถานะ Server, Bridge และระบบเสียงแบบสด", "Live server, bridge and voice diagnostics"));

        var searchRow = new LinearLayout(this) { Orientation = Orientation.Horizontal };
        searchRow.SetGravity(GravityFlags.CenterVertical);
        _logSearch = Input(string.Empty, InputTypes.ClassText);
        _logSearch.Hint = T("ค้นหา log...", "Search logs...");
        _logSearch.TextChanged += (_, _) => RefreshLog(true);
        searchRow.AddView(_logSearch, new LinearLayout.LayoutParams(0, Dp(48), 1f));
        var filterMenu = MakeButton("☰", primary: false, compact: true);
        filterMenu.TextSize = 21;
        WireButton(filterMenu, () => ShowLogFilterMenu(filterMenu));
        searchRow.AddView(filterMenu, new LinearLayout.LayoutParams(Dp(56), Dp(48)) { LeftMargin = Dp(8) });
        body.AddView(searchRow, new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MatchParent, Dp(48)) { BottomMargin = Dp(12) });

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
    text = sub_required(
        text,
        r"    private ScrollView BuildLogs\(\)\n    \{.*?\n    \}\n\n(?=    private ScrollView BuildSettings\(\))",
        logs,
        "compact log search/filter controls",
    )

    log_methods = '''    private void ShowLogFilterMenu(View anchor)
    {
        var popup = new global::Android.Widget.PopupMenu(this, anchor);
        popup.Menu.Add(0, 1, 0, (_logFilter == "ALL" ? "✓ " : string.Empty) + T("ทั้งหมด", "All"));
        popup.Menu.Add(0, 2, 1, (_logFilter == "SERVER" ? "✓ " : string.Empty) + "Server");
        popup.Menu.Add(0, 3, 2, (_logFilter == "BRIDGE" ? "✓ " : string.Empty) + "Bridge");
        popup.Menu.Add(0, 4, 3, (_logFilter == "VOICE" ? "✓ " : string.Empty) + "Voice");
        popup.MenuItemClick += (_, e) =>
        {
            _logFilter = e.Item.ItemId switch
            {
                2 => "SERVER",
                3 => "BRIDGE",
                4 => "VOICE",
                _ => "ALL"
            };
            RefreshLog(true);
        };
        popup.Show();
    }

    private static bool HasLogCategory(string row, string category) =>
        row.Contains($" {category}:", StringComparison.OrdinalIgnoreCase);

    private static bool IsRoutineUiLogRow(string row)
    {
        if (!HasLogCategory(row, "UI"))
            return false;
        return row.Contains("CLICK:", StringComparison.OrdinalIgnoreCase)
            || row.Contains("opened", StringComparison.OrdinalIgnoreCase)
            || row.Contains("pressed", StringComparison.OrdinalIgnoreCase);
    }

    private static bool MatchesLogFilter(string row, string filter) => filter switch
    {
        "SERVER" => HasLogCategory(row, "SERVICE")
            || HasLogCategory(row, "RUNTIME")
            || HasLogCategory(row, "SERVER")
            || HasLogCategory(row, "FATAL")
            || HasLogCategory(row, "HELP")
            || HasLogCategory(row, "MCHTTP")
            || HasLogCategory(row, "SECURITY"),
        "BRIDGE" => HasLogCategory(row, "BRIDGE"),
        "VOICE" => HasLogCategory(row, "VOICE"),
        _ => true
    };

    private string LocalizeLogText(string text)
    {
        if (!_thai || string.IsNullOrWhiteSpace(text))
            return text;
        return RuntimeDiagnostics.TranslateSnapshot(text, true)
            .Replace(" HELP: ", " คำแนะนำ: ", StringComparison.OrdinalIgnoreCase)
            .Replace(" | Cause: ", " | สาเหตุ: ", StringComparison.OrdinalIgnoreCase)
            .Replace(" | Fix: ", " | วิธีแก้: ", StringComparison.OrdinalIgnoreCase);
    }

    private void RefreshLog(bool force = false)
    {
        if (_logView == null || _logPaused)
            return;
        var version = AndroidRuntimeLog.Version;
        if (!force && version == _renderedLogVersion)
            return;
        _renderedLogVersion = version;

        var raw = AndroidRuntimeLog.Snapshot(false);
        var rows = string.IsNullOrWhiteSpace(raw)
            ? Array.Empty<string>()
            : raw.Split(Environment.NewLine, StringSplitOptions.RemoveEmptyEntries)
                .Where(row => !IsRoutineUiLogRow(row))
                .Where(row => MatchesLogFilter(row, _logFilter))
                .ToArray();

        var text = LocalizeLogText(string.Join(Environment.NewLine, rows));
        var query = _logSearch?.Text?.Trim();
        if (!string.IsNullOrWhiteSpace(query) && !string.IsNullOrWhiteSpace(text))
        {
            text = string.Join(
                Environment.NewLine,
                text.Split(Environment.NewLine, StringSplitOptions.RemoveEmptyEntries)
                    .Where(row => row.Contains(query, StringComparison.OrdinalIgnoreCase)));
        }

        _logView.Text = string.IsNullOrWhiteSpace(text)
            ? T("(ไม่พบ Log ที่ตรงเงื่อนไข)", "(no matching log entries)")
            : text;
    }

'''
    text = sub_required(
        text,
        r"    private void RefreshLog\(bool force = false\)\n    \{.*?\n    \}\n\n(?=    private void Pulse)",
        log_methods,
        "runtime log filtering",
    )

    text = text.replace(
        '        if (_address != null)\n            _address.Text = $"{ip}:{port}";',
        '        if (_address != null)\n            _address.Text = ip;\n        if (_portAddress != null)\n            _portAddress.Text = port.ToString();',
        1,
    )

    text = text.replace('        AndroidRuntimeLog.Append("UI", "ModernMainActivity opened");\n', "", 1)
    text = text.replace('        AndroidRuntimeLog.Append("UI", "START SERVER pressed");\n', "", 1)
    text = text.replace('        AndroidRuntimeLog.Append("UI", "STOP SERVER pressed");\n', "", 1)
    text = text.replace(
        '            AndroidRuntimeLog.Append("UI", $"START BLOCKED: {issues.Count} required setting(s) incomplete");',
        '            AndroidRuntimeLog.Append("SERVER", $"Startup blocked: {issues.Count} required setting(s) incomplete");',
        1,
    )

    path.write_text(text, encoding="utf-8")

    final = path.read_text(encoding="utf-8")
    required = [
        'private TextView? _portAddress;',
        'T("คัดลอก IP", "COPY IP")',
        'T("คัดลอก Port", "COPY PORT")',
        'private void ShowLogFilterMenu(View anchor)',
        'MakeButton("☰"',
        '"SERVER" => HasLogCategory(row, "SERVICE")',
        'AndroidRuntimeLog.Append("SERVER", $"Startup blocked:',
    ]
    missing = [value for value in required if value not in final]
    if missing:
        raise RuntimeError(f"UI5 refinement validation failed: {missing}")
    if 'voice.AddView(SectionTitle(T("เซิร์ฟเวอร์เสียง", "Voice Server")' in final:
        raise RuntimeError("Legacy Voice Server setup card still present")
    if 'T("คัดลอก IP:Port", "COPY IP:PORT")' in final:
        raise RuntimeError("Combined IP:Port copy action still present")

    print(f"Applied UI5 dashboard/log refinement to {path}")


if __name__ == "__main__":
    main()
