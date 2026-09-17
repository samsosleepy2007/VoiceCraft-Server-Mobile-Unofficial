#!/usr/bin/env python3
from pathlib import Path
import re
import sys

MARKER = "MCSV_INSTALL_DETAILED_LOGGING"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"MCSV detailed-log patch anchor mismatch ({count}): {label}")
    return text.replace(old, new, 1)


def insert_after_once(text: str, anchor: str, insertion: str, label: str) -> str:
    count = text.count(anchor)
    if count != 1:
        raise RuntimeError(f"MCSV detailed-log insertion anchor mismatch ({count}): {label}")
    return text.replace(anchor, anchor + insertion, 1)


def main() -> None:
    repo = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
    installer = repo / "VoiceCraft.Server.Android" / "McsvVoiceCraftInstaller.cs"
    activity = repo / "VoiceCraft.Server.Android" / "ModernMainActivity.cs"
    logger = repo / "VoiceCraft.Server.Android" / "McsvInstallLogger.cs"

    for path in (installer, activity, logger):
        if not path.exists():
            raise SystemExit(f"Required MCSV detailed-log file missing: {path}")

    text = installer.read_text(encoding="utf-8")
    if MARKER in text:
        print("MCSV detailed installer logging already applied")
        return

    text = replace_once(
        text,
        '''        progress ??= _ => { };
        using var api = new McsvApiClient(apiKey);
''',
        '''        // MCSV_INSTALL_DETAILED_LOGGING
        var uiProgress = progress ?? (_ => { });
        McsvInstallLogger.Begin();
        progress = message =>
        {
            McsvInstallLogger.Progress(message);
            uiProgress(message);
        };
        using var api = new McsvApiClient(apiKey);
''',
        "wrap installer progress in safe runtime logging",
    )

    text = insert_after_once(
        text,
        '        await api.ValidateKeyAsync(cancellationToken);\n',
        '        progress("OK — MCSV API key validated");\n',
        "API key validated",
    )

    text = replace_once(
        text,
        '''        if (missing.Length > 0)
            throw new McsvApiException(
                "MCSV API key is missing required permissions: " + string.Join(", ", missing));

        var serverInfo = McsvApiClient.UnwrapResult(
''',
        '''        if (missing.Length > 0)
            throw new McsvApiException(
                "MCSV API key is missing required permissions: " + string.Join(", ", missing));
        progress("OK — required MCSV permissions verified");

        var serverInfo = McsvApiClient.UnwrapResult(
''',
        "required permissions verified",
    )

    text = insert_after_once(
        text,
        '''        await McsvEndweaveSupport.ValidatePreflightAsync(api, serverInfo, cancellationToken);
''',
        '        progress("OK — Endstone server preflight passed");\n',
        "Endstone preflight success",
    )

    text = insert_after_once(
        text,
        '''        await McsvPythonEnvironmentValidator.ValidateAsync(
            api,
            environment,
            progress,
            cancellationToken);
''',
        '        progress("OK — Python package metadata is healthy");\n',
        "Python metadata health success",
    )

    text = insert_after_once(
        text,
        '''        await api.CallToolAsync(
            "backups_create",
            new { name = "voicecraft-endweave-v2-preinstall" },
            cancellationToken);
''',
        '        progress("OK — required safety backup created");\n',
        "backup success",
    )

    text = insert_after_once(
        text,
        '''        await McsvEndweaveInstaller.InstallAsync(
            api,
            endweaveWheel,
            progress,
            cancellationToken);
''',
        '        progress("OK — Endweave wheel staged and verified");\n',
        "Endweave success",
    )

    text = insert_after_once(
        text,
        '        await InstallPluginAsync(api, cancellationToken);\n',
        '        progress("OK — VoiceCraft Endstone plugin staged");\n',
        "VoiceCraft plugin success",
    )

    text = insert_after_once(
        text,
        '''        await WritePluginConfigAsync(
            api,
            BuildPluginConfig(relayWebSocket, backupRelays, serverId, bridgeSecret),
            cancellationToken);
''',
        '        progress("OK — VoiceCraft relay/config file written");\n',
        "VoiceCraft config success",
    )

    text = insert_after_once(
        text,
        '''        await McsvInstallVerifier.VerifyItemMicFilesAsync(
            api,
            progress,
            cancellationToken);
''',
        '        progress("OK — Item Mic Behavior/Resource Packs verified");\n',
        "Item Mic verification success",
    )

    text = insert_after_once(
        text,
        '''        await McsvInstallVerifier.VerifyConfigAndActiveWorldAsync(
            api,
            serverId,
            progress,
            cancellationToken);
''',
        '        progress("OK — config and active-world pack JSON verified");\n',
        "world/config verification success",
    )

    text = insert_after_once(
        text,
        '''        await api.CallToolAsync(
            "power_action",
            new { action = "restart" },
            cancellationToken);
''',
        '        progress("OK — restart command accepted by MCSV");\n',
        "restart accepted",
    )

    text = insert_after_once(
        text,
        '''        if (!running)
            throw new McsvApiException(
                "MCSV server did not return to Running state within the verification window after restart.");
''',
        '        progress("OK — MCSV server returned to Running state");\n',
        "running state success",
    )

    text = insert_after_once(
        text,
        '''        await McsvStartupVerifier.VerifyAsync(
            api,
            progress,
            cancellationToken);
''',
        '        progress("OK — startup log confirms Endweave + VoiceCraft loaded");\n',
        "startup verifier success",
    )

    installer.write_text(text, encoding="utf-8")

    ui = activity.read_text(encoding="utf-8")
    ui = replace_once(
        ui,
        '            AndroidRuntimeLog.Append("MCSV", $"Install failed: {message}");\n',
        '            McsvInstallLogger.Failure(ex);\n',
        "route install failures through structured MCSV logger",
    )

    diagnostics_pattern = re.compile(
        r'(private ScrollView BuildLogs\(\).*?var \(scroll, body\) = NewPage\(\s*'
        r'T\("[^"]*",\s*"[^"]*"\),\s*)'
        r'T\("[^"]*",\s*"[^"]*"\)\);',
        re.S,
    )
    diagnostics_replacement = (
        r'\1T("ดูเหตุการณ์ล่าสุด รวมขั้นตอน MCSV INSTALL, OK, WARN, ERROR และคำแนะนำการแก้ไข", '
        r'"Inspect recent activity including MCSV INSTALL steps, OK, WARN, ERROR, and suggested fixes"));'
    )
    ui, count = diagnostics_pattern.subn(diagnostics_replacement, ui, count=1)
    if count != 1:
        raise RuntimeError("MCSV detailed-log patch could not locate BuildLogs subtitle")

    activity.write_text(ui, encoding="utf-8")

    final = installer.read_text(encoding="utf-8")
    final_ui = activity.read_text(encoding="utf-8")
    required = [
        MARKER,
        "McsvInstallLogger.Begin()",
        "McsvInstallLogger.Progress(message)",
        "OK — MCSV API key validated",
        "OK — required MCSV permissions verified",
        "OK — Endstone server preflight passed",
        "OK — Python package metadata is healthy",
        "OK — required safety backup created",
        "OK — Endweave wheel staged and verified",
        "OK — VoiceCraft Endstone plugin staged",
        "OK — Item Mic Behavior/Resource Packs verified",
        "OK — config and active-world pack JSON verified",
        "OK — MCSV server returned to Running state",
        "OK — startup log confirms Endweave + VoiceCraft loaded",
    ]
    missing = [marker for marker in required if marker not in final]
    if missing:
        raise RuntimeError(f"MCSV detailed installer logging incomplete: {missing}")

    if "McsvInstallLogger.Failure(ex)" not in final_ui:
        raise RuntimeError("MCSV detailed installer failure logging is not wired to the UI")
    if "MCSV INSTALL, OK, WARN, ERROR" not in final_ui:
        raise RuntimeError("Runtime Logs page does not explain MCSV installer log states")

    print(f"Applied detailed MCSV installer logging to {installer}")
    print(f"Wired MCSV failure diagnostics + Runtime Logs UI help in {activity}")


if __name__ == "__main__":
    main()
