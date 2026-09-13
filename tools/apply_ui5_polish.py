#!/usr/bin/env python3
from pathlib import Path
import re
import sys


def replace_required(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise RuntimeError(f"UI5 polish failed: {label}")
    return text.replace(old, new, 1)


def sub_required(text: str, pattern: str, replacement: str, label: str) -> str:
    changed, count = re.subn(pattern, replacement, text, count=1, flags=re.S)
    if count != 1:
        raise RuntimeError(f"UI5 polish failed: {label} ({count})")
    return changed


def main() -> None:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
    path = root / "VoiceCraft.Server.Android" / "ModernMainActivity.cs"
    text = path.read_text(encoding="utf-8")

    # 1) Render Relay: remove the decorative always-connected green badge.
    # Runtime relay state is still available on Dashboard and Runtime Logs.
    relay_with_badge = '''        var relay = Card();
        var relayHead = new LinearLayout(this) { Orientation = Orientation.Horizontal };
        relayHead.SetGravity(GravityFlags.CenterVertical);
        relayHead.AddView(SectionTitle("Render Relay", Primary), new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WrapContent, 1f));
        relayHead.AddView(Pill(T("● เชื่อมต่อ", "● CONNECTED"), SuccessFill, Green, true), new LinearLayout.LayoutParams(ViewGroup.LayoutParams.WrapContent, Dp(30)));
        relay.AddView(relayHead);
'''
    relay_plain = '''        var relay = Card();
        relay.AddView(SectionTitle("Render Relay", Primary));
'''
    text = replace_required(text, relay_with_badge, relay_plain, "remove Render Relay connected badge")

    # 2) Endstone Integration: remove the decorative bridge-connected text.
    # Real bridge state remains visible from Dashboard and Runtime Logs.
    endstone_connected = '''        endstone.AddView(Label(T("● Minecraft bridge connected", "● Minecraft bridge connected"), 11, Green, true), Top(Dp(8)));
'''
    text = replace_required(text, endstone_connected, "", "remove Endstone bridge connected text")

    # 3) Dashboard: keep ONLINE/OFFLINE in the same address panel as IP/Port,
    # and remove the decorative progress bar under the server status card.
    old_top_status = '''        var onlineRow = new LinearLayout(this) { Orientation = Orientation.Horizontal };
        onlineRow.SetGravity(GravityFlags.CenterVertical);
        _statusBadge = Pill(T("● ออฟไลน์", "● OFFLINE"), _dark ? Color.Rgb(20, 58, 48) : Color.Rgb(229, 249, 239), Green, true);
        onlineRow.AddView(_statusBadge, new LinearLayout.LayoutParams(ViewGroup.LayoutParams.WrapContent, Dp(32)));
        body.AddView(onlineRow, Top(Dp(2)));
        body.AddView(Label("VoiceCraft Server", 18, Ink, true), Top(Dp(12)));
'''
    new_top_status = '''        body.AddView(Label("VoiceCraft Server", 18, Ink, true), Top(Dp(2)));
'''
    text = replace_required(text, old_top_status, new_top_status, "move dashboard status badge")

    address_title = '''        addressBox.SetPadding(Dp(14), Dp(12), Dp(14), Dp(12));
        addressBox.AddView(Label(T("ที่อยู่เซิร์ฟเวอร์", "SERVER ADDRESS"), 10, Primary, true));
'''
    address_with_status = '''        addressBox.SetPadding(Dp(14), Dp(12), Dp(14), Dp(12));
        addressBox.AddView(Label(T("ที่อยู่เซิร์ฟเวอร์", "SERVER ADDRESS"), 10, Primary, true));

        var statusRow = new LinearLayout(this) { Orientation = Orientation.Horizontal };
        statusRow.SetGravity(GravityFlags.CenterVertical);
        statusRow.AddView(Label(T("สถานะ", "STATUS"), 10, Muted, true), new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WrapContent, 1f));
        _statusBadge = Pill(T("● ออฟไลน์", "● OFFLINE"), _dark ? Color.Rgb(20, 58, 48) : Color.Rgb(229, 249, 239), Green, true);
        statusRow.AddView(_statusBadge, new LinearLayout.LayoutParams(ViewGroup.LayoutParams.WrapContent, Dp(32)));
        addressBox.AddView(statusRow, Top(Dp(10)));
'''
    text = replace_required(text, address_title, address_with_status, "add status badge to address panel")

    progress = '''        var progress = new ProgressBar(this, null, global::Android.Resource.Attribute.ProgressBarStyleHorizontal)
        {
            Indeterminate = false,
            Progress = 72,
            Max = 100
        };
        running.AddView(progress, new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MatchParent, Dp(5)) { TopMargin = Dp(14) });
'''
    text = replace_required(text, progress, "", "remove dashboard progress bar")

    # 4) Runtime Logs: color each visible line by meaning.
    # Priority is red errors, explicit green success, yellow reconnect/failover,
    # then white for ordinary runtime status.
    colored_refresh = '''    private Color LogColorForRow(string row)
    {
        var value = row ?? string.Empty;

        // The local McHttp health probe intentionally sends an unauthenticated
        // GET / request. A 401/403 proves the listener answered and is not a
        // runtime failure, so keep this specific probe response neutral.
        if (value.Contains("McHttp raw HTTP response:", StringComparison.OrdinalIgnoreCase)
            && (value.Contains("403 Forbidden", StringComparison.OrdinalIgnoreCase)
                || value.Contains("401 Unauthorized", StringComparison.OrdinalIgnoreCase)))
            return Color.White;

        if (HasLogCategory(value, "FATAL")
            || value.Contains(" error", StringComparison.OrdinalIgnoreCase)
            || value.Contains("exception", StringComparison.OrdinalIgnoreCase)
            || value.Contains("fatal", StringComparison.OrdinalIgnoreCase)
            || value.Contains("failed", StringComparison.OrdinalIgnoreCase)
            || value.Contains("failure", StringComparison.OrdinalIgnoreCase)
            || value.Contains("unauthorized", StringComparison.OrdinalIgnoreCase)
            || value.Contains("forbidden", StringComparison.OrdinalIgnoreCase)
            || value.Contains("invalid", StringComparison.OrdinalIgnoreCase)
            || value.Contains("unable to", StringComparison.OrdinalIgnoreCase)
            || value.Contains("cannot ", StringComparison.OrdinalIgnoreCase))
            return Red;

        if (value.Contains("connected successfully", StringComparison.OrdinalIgnoreCase)
            || value.Contains("reconnected successfully", StringComparison.OrdinalIgnoreCase)
            || value.Contains("connection established", StringComparison.OrdinalIgnoreCase)
            || value.Contains("bridge connected", StringComparison.OrdinalIgnoreCase)
            || value.Contains("relay connected", StringComparison.OrdinalIgnoreCase)
            || value.Contains("voice client connected", StringComparison.OrdinalIgnoreCase)
            || value.Contains("bound successfully", StringComparison.OrdinalIgnoreCase))
            return Green;

        if (value.Contains("disconnected", StringComparison.OrdinalIgnoreCase)
            || value.Contains("connection lost", StringComparison.OrdinalIgnoreCase)
            || value.Contains("retrying", StringComparison.OrdinalIgnoreCase)
            || value.Contains("retry ", StringComparison.OrdinalIgnoreCase)
            || value.Contains("reconnecting", StringComparison.OrdinalIgnoreCase)
            || value.Contains("switching relay", StringComparison.OrdinalIgnoreCase)
            || value.Contains("failover", StringComparison.OrdinalIgnoreCase)
            || value.Contains("timed out", StringComparison.OrdinalIgnoreCase)
            || value.Contains("timeout", StringComparison.OrdinalIgnoreCase))
            return Amber;

        if (value.Contains(" connected", StringComparison.OrdinalIgnoreCase)
            || value.Contains("online", StringComparison.OrdinalIgnoreCase)
            || value.Contains("ready", StringComparison.OrdinalIgnoreCase))
            return Green;

        return Color.White;
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
            : raw.Split(global::System.Environment.NewLine, StringSplitOptions.RemoveEmptyEntries)
                .Where(row => !IsRoutineUiLogRow(row))
                .Where(row => MatchesLogFilter(row, _logFilter))
                .ToArray();

        var query = _logSearch?.Text?.Trim();
        var visible = new List<(string Text, Color Color)>();
        foreach (var row in rows)
        {
            var display = LocalizeLogText(row);
            if (!string.IsNullOrWhiteSpace(query)
                && !display.Contains(query, StringComparison.OrdinalIgnoreCase))
                continue;
            visible.Add((display, LogColorForRow(row)));
        }

        if (visible.Count == 0)
        {
            _logView.Text = T("(ไม่พบ Log ที่ตรงเงื่อนไข)", "(no matching log entries)");
            _logView.SetTextColor(Color.White);
            return;
        }

        var combined = string.Join(global::System.Environment.NewLine, visible.Select(entry => entry.Text));
        var styled = new global::Android.Text.SpannableStringBuilder(combined);
        var offset = 0;
        foreach (var entry in visible)
        {
            var end = offset + entry.Text.Length;
            styled.SetSpan(
                new global::Android.Text.Style.ForegroundColorSpan(entry.Color),
                offset,
                end,
                global::Android.Text.SpanTypes.ExclusiveExclusive);
            offset = end + global::System.Environment.NewLine.Length;
        }
        _logView.TextFormatted = styled;
    }

'''
    text = sub_required(
        text,
        r"    private void RefreshLog\(bool force = false\)\n    \{.*?\n    \}\n\n(?=    private void Pulse)",
        colored_refresh,
        "colored runtime logs",
    )

    # 5) Runtime Logs: remove the pause control so live logs always update.
    pause_button = '''        AddButton(buttons, T("หยุดชั่วคราว", "PAUSE"), () => { _logPaused = !_logPaused; RefreshLog(true); });
'''
    text = replace_required(text, pause_button, "", "remove log pause button")

    path.write_text(text, encoding="utf-8")
    print(f"Applied UI5 polish to {path}")
    print("- removed decorative Render Relay connected badge")
    print("- removed decorative Endstone bridge connected text")
    print("- moved ONLINE/OFFLINE into the server address panel")
    print("- removed dashboard progress bar")
    print("- added white/green/yellow/red runtime log colors")
    print("- removed log pause control")
    print("- treated expected McHttp probe 401/403 as normal")


if __name__ == "__main__":
    main()
