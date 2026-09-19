#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import re
import sys

REPO_RELEASE_BASE = (
    "https://github.com/samsosleepy2007/"
    "VoiceCraft-Server-Mobile-Unofficial/releases/latest/download/"
)
PLUGIN_NAME = "endstone_voicecraft-0.2.17-py3-none-any.whl"
PLUGIN_SHA256 = "4d8895fa653a6c01f0d935f648be7b4e94357999663c5358a0280f55a99f9e1c"
ADDON_NAME = "VoiceCraft_ItemMic_v2.6.10_DDUI-Bind.mcaddon"
ITEM_MIC_BP_PACK = "VoiceCraft_ItemMic_BP_v2.6.10.mcpack"
ITEM_MIC_RP_PACK = "VoiceCraft_ItemMic_RP_v2.6.10.mcpack"


def replace_string_constant(text: str, name: str, value: str) -> str:
    pattern = re.compile(
        rf'(^\s*private const string {re.escape(name)} = ")[^"]*(";)',
        re.MULTILINE,
    )
    text, count = pattern.subn(rf'\g<1>{value}\g<2>', text, count=1)
    if count != 1:
        raise RuntimeError(f"could not replace string constant {name}")
    return text


def replace_declaration_block(text: str, name: str, replacement: str) -> str:
    marker = f"    private const string {name} ="
    start = text.find(marker)
    if start < 0:
        raise RuntimeError(f"could not find declaration {name}")
    end = text.find(";", start)
    if end < 0:
        raise RuntimeError(f"unterminated declaration {name}")
    return text[:start] + replacement + text[end + 1:]


def patch_installer(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    text = replace_string_constant(text, "PluginWheelName", PLUGIN_NAME)
    text = replace_declaration_block(
        text,
        "PluginWheelUrl",
        (
            '    private const string PluginWheelUrl =\n'
            f'        "{REPO_RELEASE_BASE}" +\n'
            '        PluginWheelName;'
        ),
    )
    text = replace_declaration_block(
        text,
        "ItemMicUrl",
        (
            '    private const string ItemMicUrl =\n'
            f'        "{REPO_RELEASE_BASE}{ADDON_NAME}";'
        ),
    )
    text = replace_string_constant(text, "ItemMicBpPack", ITEM_MIC_BP_PACK)
    text = replace_string_constant(text, "ItemMicRpPack", ITEM_MIC_RP_PACK)
    path.write_text(text, encoding="utf-8")


def patch_configured_downloader(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    text = replace_string_constant(text, "WheelFileName", PLUGIN_NAME)
    text = replace_string_constant(text, "SourceWheelSha256", PLUGIN_SHA256)
    text = replace_declaration_block(
        text,
        "SourceWheelUrl",
        (
            '    private const string SourceWheelUrl =\n'
            f'        "{REPO_RELEASE_BASE}" +\n'
            '        WheelFileName;'
        ),
    )
    path.write_text(text, encoding="utf-8")


def patch_item_mic_verifier(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    text, count = re.subn(
        r"new\[\]\s*\{\s*2\s*,\s*4\s*,\s*0\s*\}",
        "new[] { 2, 6, 10 }",
        text,
    )
    if count < 1 and "new[] { 2, 6, 10 }" not in text:
        raise RuntimeError("could not update Item Mic version verification")
    text = text.replace("expected VoiceCraft 2.4.0 pack", "expected VoiceCraft 2.6.10 pack")
    text = text.replace("is not 2.4.0.", "is not 2.6.10.")
    path.write_text(text, encoding="utf-8")


def validate(path: Path, required: tuple[str, ...]) -> None:
    text = path.read_text(encoding="utf-8")
    missing = [value for value in required if value not in text]
    if missing:
        raise RuntimeError(f"V3.0.2 release-channel validation failed for {path}: {missing}")


def main() -> None:
    repo = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
    installer = repo / "VoiceCraft.Server.Android" / "McsvVoiceCraftInstaller.cs"
    configured = repo / "VoiceCraft.Server.Android" / "ConfiguredPluginDownloadInjector.cs"
    verifier = repo / "VoiceCraft.Server.Android" / "McsvInstallVerifier.cs"

    for path in (installer, configured, verifier):
        if not path.exists():
            raise SystemExit(f"generated Android integration file not found: {path}")

    patch_installer(installer)
    patch_configured_downloader(configured)
    patch_item_mic_verifier(verifier)

    validate(
        installer,
        (REPO_RELEASE_BASE, PLUGIN_NAME, ADDON_NAME, ITEM_MIC_BP_PACK, ITEM_MIC_RP_PACK),
    )
    validate(
        configured,
        (REPO_RELEASE_BASE, PLUGIN_NAME, PLUGIN_SHA256),
    )
    validate(
        verifier,
        ("new[] { 2, 6, 10 }", "2.6.10"),
    )

    print("Applied/verified VoiceCraft MCSV V3.0.2 release channel")


if __name__ == "__main__":
    main()
