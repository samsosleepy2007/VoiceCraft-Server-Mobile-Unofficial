#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import re
import sys

REPO_RELEASE_BASE = (
    "https://github.com/samsosleepy2007/"
    "VoiceCraft-Server-Mobile-Unofficial/releases/latest/download/"
)
PLUGIN_NAME = "endstone_voicecraft-0.2.8-py3-none-any.whl"
PLUGIN_SHA256 = "b6ac91c8e02441edb2476af3c473f58baf70fd99189c702342389931997840ea"
ADDON_NAME = "VoiceCraft_ItemMic_v2.4.0.mcaddon"

STALE_RELEASE_MARKERS = (
    "v1.7.1-itemmic2.4.0-hidden-single",
    "v1.7.1-android-phase2-ui5-voice-range-strongfade50-endstone0.2.8-relay0.2.1-itemmic2.3.0",
    "v1.7.1-android-phase2-ui4.5.2-account-v2-guest-endstone0.2.6-relay0.2.1",
)


def replace_exact(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"release-channel patch anchor mismatch ({count}): {label}")
    return text.replace(old, new, 1)


def patch_installer(path: Path) -> None:
    text = path.read_text(encoding="utf-8")

    plugin_pattern = re.compile(
        r'    private const string PluginWheelUrl =\n'
        r'        "https://github\.com/samsosleepy2007/VoiceCraft-Server-Mobile-Unofficial/releases/download/" \+\n'
        r'        "[^"]+/" \+\n'
        r'        PluginWheelName;'
    )
    replacement = (
        '    private const string PluginWheelUrl =\n'
        f'        "{REPO_RELEASE_BASE}" +\n'
        '        PluginWheelName;'
    )
    text, count = plugin_pattern.subn(replacement, text, count=1)
    if count != 1:
        raise RuntimeError("could not replace MCSV PluginWheelUrl")

    item_pattern = re.compile(
        r'    private const string ItemMicUrl =\n'
        r'        "https://github\.com/samsosleepy2007/VoiceCraft-Server-Mobile-Unofficial/releases/download/" \+\n'
        r'        "[^"]+/VoiceCraft_ItemMic_v2\.4\.0\.mcaddon";'
    )
    replacement = (
        '    private const string ItemMicUrl =\n'
        f'        "{REPO_RELEASE_BASE}{ADDON_NAME}";'
    )
    text, count = item_pattern.subn(replacement, text, count=1)
    if count != 1:
        raise RuntimeError("could not replace MCSV ItemMicUrl")

    path.write_text(text, encoding="utf-8")


def patch_configured_downloader(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    text = replace_exact(
        text,
        '    private const string WheelFileName = "endstone_voicecraft-0.2.6-py3-none-any.whl";',
        f'    private const string WheelFileName = "{PLUGIN_NAME}";',
        "configured plugin wheel version",
    )
    text = replace_exact(
        text,
        '    private const string SourceWheelSha256 = "b6725cc94609d27b3d2815f66e1373fe8c6917d7be68562456ac7727254e8ae4";',
        f'    private const string SourceWheelSha256 = "{PLUGIN_SHA256}";',
        "configured plugin SHA-256",
    )

    url_pattern = re.compile(
        r'    private const string SourceWheelUrl =\n'
        r'        "https://github\.com/samsosleepy2007/VoiceCraft-Server-Mobile-Unofficial/releases/download/" \+\n'
        r'        "[^"]+/" \+\n'
        r'        WheelFileName;'
    )
    replacement = (
        '    private const string SourceWheelUrl =\n'
        f'        "{REPO_RELEASE_BASE}" +\n'
        '        WheelFileName;'
    )
    text, count = url_pattern.subn(replacement, text, count=1)
    if count != 1:
        raise RuntimeError("could not replace configured plugin SourceWheelUrl")

    path.write_text(text, encoding="utf-8")


def validate(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    for marker in STALE_RELEASE_MARKERS:
        if marker in text:
            raise RuntimeError(f"stale deleted-release marker remains in {path}: {marker}")


def main() -> None:
    repo = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
    installer = repo / "VoiceCraft.Server.Android" / "McsvVoiceCraftInstaller.cs"
    configured = repo / "VoiceCraft.Server.Android" / "ConfiguredPluginDownloadInjector.cs"

    if not installer.exists():
        raise SystemExit(f"generated MCSV installer not found: {installer}")
    if not configured.exists():
        raise SystemExit(f"configured plugin downloader not found: {configured}")

    patch_installer(installer)
    patch_configured_downloader(configured)
    validate(installer)
    validate(configured)

    installer_text = installer.read_text(encoding="utf-8")
    configured_text = configured.read_text(encoding="utf-8")
    required = (
        REPO_RELEASE_BASE,
        PLUGIN_NAME,
        ADDON_NAME,
    )
    missing = [value for value in required if value not in installer_text + configured_text]
    if missing:
        raise RuntimeError(f"release-channel validation failed: {missing}")
    if PLUGIN_SHA256 not in configured_text:
        raise RuntimeError("configured plugin SHA-256 validation failed")

    print("Applied VoiceCraft MCSV V3.0.1 latest-release channel hotfix")


if __name__ == "__main__":
    main()
