#!/usr/bin/env python3
from pathlib import Path
import sys


AVATAR_URL = "https://avatars.githubusercontent.com/u/235958240?v=4"
PROFILE_NAME = "SamSoSleepy"


def replace_required(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise RuntimeError(f"Dashboard profile avatar patch failed: {label}")
    return text.replace(old, new, 1)


def main() -> None:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
    path = root / "VoiceCraft.Server.Android" / "ModernMainActivity.cs"
    text = path.read_text(encoding="utf-8")

    badge_old = '''        var vc = Pill("VC", _dark ? Color.Rgb(18, 55, 96) : Color.Rgb(231, 242, 254), Primary, true);
        vc.TextSize = 13;
        runningRow.AddView(vc, new LinearLayout.LayoutParams(Dp(54), Dp(54)) { RightMargin = Dp(14) });
'''
    badge_new = '''        var profileBadge = new FrameLayout(this)
        {
            Background = Round(_dark ? Color.Rgb(18, 55, 96) : Color.Rgb(231, 242, 254), 16, Border)
        };
        var profileFallback = Label("SS", 13, Primary, true);
        profileFallback.Gravity = GravityFlags.Center;
        profileFallback.ContentDescription = "SamSoSleepy GitHub profile";
        profileBadge.AddView(profileFallback, new FrameLayout.LayoutParams(
            ViewGroup.LayoutParams.MatchParent,
            ViewGroup.LayoutParams.MatchParent));

        var profileAvatar = new ImageView(this)
        {
            Visibility = ViewStates.Invisible,
            Background = Round(SurfaceSoft, 16, Border),
            ClipToOutline = true,
            ContentDescription = "SamSoSleepy GitHub profile picture"
        };
        profileAvatar.SetScaleType(ImageView.ScaleType.CenterCrop);
        profileBadge.AddView(profileAvatar, new FrameLayout.LayoutParams(
            ViewGroup.LayoutParams.MatchParent,
            ViewGroup.LayoutParams.MatchParent));
        runningRow.AddView(profileBadge, new LinearLayout.LayoutParams(Dp(54), Dp(54)) { RightMargin = Dp(14) });
        _ = LoadDashboardProfileAvatarAsync(profileAvatar);
'''
    text = replace_required(text, badge_old, badge_new, "replace VC badge")

    methods_anchor = "    private void ShowOpenSourceLegal()\n"
    avatar_method = f'''    private async Task LoadDashboardProfileAvatarAsync(ImageView profileAvatar)\n    {{\n        try\n        {{\n            using var client = new System.Net.Http.HttpClient\n            {{\n                Timeout = TimeSpan.FromSeconds(6)\n            }};\n            client.DefaultRequestHeaders.UserAgent.ParseAdd("VoiceCraft-Server-Mobile/1.0");\n            using var response = await client.GetAsync("{AVATAR_URL}");\n            response.EnsureSuccessStatusCode();\n            var bytes = await response.Content.ReadAsByteArrayAsync();\n            var bitmap = global::Android.Graphics.BitmapFactory.DecodeByteArray(bytes, 0, bytes.Length);\n            if (bitmap == null)\n                return;\n\n            RunOnUiThread(() =>\n            {{\n                if (IsFinishing || IsDestroyed)\n                    return;\n                profileAvatar.SetImageBitmap(bitmap);\n                profileAvatar.Visibility = ViewStates.Visible;\n            }});\n        }}\n        catch (Exception ex)\n        {{\n            AndroidRuntimeLog.Append("UI", $"GitHub profile avatar unavailable: {{ex.GetType().Name}}");\n        }}\n    }}\n\n'''
    text = replace_required(text, methods_anchor, avatar_method + methods_anchor, "avatar loader method")

    path.write_text(text, encoding="utf-8")
    final = path.read_text(encoding="utf-8")
    required = [
        "SamSoSleepy GitHub profile picture",
        "LoadDashboardProfileAvatarAsync(profileAvatar)",
        AVATAR_URL,
        "profileAvatar.Visibility = ViewStates.Visible",
    ]
    missing = [value for value in required if value not in final]
    if missing:
        raise RuntimeError(f"Dashboard profile avatar validation failed: {missing}")
    if 'var vc = Pill("VC"' in final:
        raise RuntimeError("Dashboard profile avatar validation failed: old VC badge still present")

    print(f"Applied Dashboard GitHub profile avatar to {path}")
    print(f"- profile: {PROFILE_NAME}")
    print("- loads the GitHub avatar without blocking Dashboard startup")
    print("- keeps SS initials as an offline/network fallback")


if __name__ == "__main__":
    main()
