#!/usr/bin/env python3
from pathlib import Path
import re
import sys


SETTINGS_ACTION_HELPER = r'''    private View SettingsAction(string title, string subtitle, string action, Action onClick)
    {
        var row = new LinearLayout(this)
        {
            Orientation = Orientation.Horizontal,
            Background = Round(SurfaceSoft, 16, Border)
        };
        row.SetGravity(GravityFlags.CenterVertical);
        row.SetPadding(Dp(14), Dp(12), Dp(10), Dp(12));

        var copy = new LinearLayout(this) { Orientation = Orientation.Vertical };
        copy.AddView(Label(title, 13, Ink, true));
        copy.AddView(Label(subtitle, 10, Muted), Top(Dp(3)));
        row.AddView(copy, new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WrapContent, 1f));

        var button = MakeButton(action, primary: false, compact: true);
        WireButton(button, onClick);
        row.AddView(button, new LinearLayout.LayoutParams(Dp(100), Dp(42)) { LeftMargin = Dp(8) });
        return row;
    }

'''


def main() -> None:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
    path = root / "VoiceCraft.Server.Android" / "ModernMainActivity.cs"
    text = path.read_text(encoding="utf-8")

    broken_split = "text.Split('" + "\n" + "');"
    broken_join = 'text = string.Join("' + "\n" + '", rows);'

    if broken_split in text:
        text = text.replace(
            broken_split,
            "text.Split(global::System.Environment.NewLine, StringSplitOptions.None);",
            1,
        )
    if broken_join in text:
        text = text.replace(
            broken_join,
            "text = string.Join(global::System.Environment.NewLine, rows);",
            1,
        )

    # ModernMainActivity imports Android.OS, which also exposes Environment.
    # Fully qualify every generated System.Environment.NewLine reference while
    # leaving already-qualified references untouched. This makes the repair
    # safe to run both before and after the UI5 refinement pass.
    text = re.sub(
        r"(?<!System\.)Environment\.NewLine",
        "global::System.Environment.NewLine",
        text,
    )

    if "private View SettingsAction(" not in text:
        marker = "    private (ScrollView Scroll, LinearLayout Body) NewPage"
        if marker not in text:
            raise RuntimeError("UI5 SettingsAction insertion anchor missing")
        text = text.replace(marker, SETTINGS_ACTION_HELPER + marker, 1)

    if broken_split in text or broken_join in text:
        raise RuntimeError("UI5 generated newline literals were not fully repaired")
    if re.search(r"(?<!System\.)Environment\.NewLine", text):
        raise RuntimeError("UI5 generated source still contains ambiguous Environment.NewLine")
    if "private View SettingsAction(" not in text:
        raise RuntimeError("UI5 SettingsAction helper missing")

    path.write_text(text, encoding="utf-8")
    print(f"Repaired UI5 generated source helpers in {path}")


if __name__ == "__main__":
    main()
