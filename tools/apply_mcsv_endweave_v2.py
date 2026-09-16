#!/usr/bin/env python3
from pathlib import Path
import sys

MARKER = "MCSV_ENDWEAVE_V2_FLOW"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"MCSV Endweave V2 patch anchor mismatch ({count}): {label}")
    return text.replace(old, new, 1)


def main() -> None:
    repo = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
    installer = repo / "VoiceCraft.Server.Android" / "McsvVoiceCraftInstaller.cs"
    if not installer.exists():
        raise SystemExit(f"McsvVoiceCraftInstaller.cs not found: {installer}")

    text = installer.read_text(encoding="utf-8")
    if MARKER in text:
        print("MCSV Endweave V2 flow already applied")
        return

    tools_anchor = '''        "files_decompress",
        "files_fetch_url",
        "power_action"
    };
'''
    tools_replacement = '''        "files_decompress",
        "files_fetch_url",
        "power_action",
        "server_overview",
        "logs_startup",
        "backups_create"
    };
'''
    text = replace_once(
        text,
        tools_anchor,
        tools_replacement,
        "V2 required permissions",
    )

    preflight_anchor = '''        if (!root.Any(entry => entry.IsFile && entry.Name.Equals("server.properties", StringComparison.Ordinal)))
            throw new McsvApiException("/server.properties was not found on this server.");

        var warning = string.Empty;
'''
    preflight_replacement = '''        if (!root.Any(entry => entry.IsFile && entry.Name.Equals("server.properties", StringComparison.Ordinal)))
            throw new McsvApiException("/server.properties was not found on this server.");

        // MCSV_ENDWEAVE_V2_FLOW
        progress("Checking Endstone runtime…");
        await McsvEndweaveSupport.ValidatePreflightAsync(api, serverInfo, cancellationToken);

        progress("Detecting server OS / Python…");
        var environment = await McsvEndweaveSupport.DetectEnvironmentAsync(
            api,
            serverInfo,
            cancellationToken);
        progress("Detected " + environment.Summary);

        await McsvPythonEnvironmentValidator.ValidateAsync(
            api,
            environment,
            progress,
            cancellationToken);

        var endweaveWheel = McsvEndweaveCatalog.SelectWheel(environment);
        progress("Selected Endweave " + endweaveWheel.PythonTag + " for " + environment.OperatingSystem + "/" + environment.Architecture);

        var warning = string.Empty;
'''
    text = replace_once(
        text,
        preflight_anchor,
        preflight_replacement,
        "runtime preflight and Endweave wheel selection",
    )

    backup_anchor = '''        var warning = string.Empty;
        if (allowedTools.Contains("backups_create"))
        {
            progress("Creating safety backup…");
            try
            {
                await api.CallToolAsync(
                    "backups_create",
                    new { name = "voicecraft-auto-install" },
                    cancellationToken);
            }
            catch (Exception ex)
            {
                warning = "Backup could not be created: " + SafeMessage(ex);
            }
        }

'''
    backup_replacement = '''        var warning = string.Empty;
        progress("Creating required safety backup…");
        await api.CallToolAsync(
            "backups_create",
            new { name = "voicecraft-endweave-v2-preinstall" },
            cancellationToken);

'''
    text = replace_once(
        text,
        backup_anchor,
        backup_replacement,
        "mandatory safety backup before installation",
    )

    install_anchor = '''        progress("Installing Endstone plugin…");
        await InstallPluginAsync(api, cancellationToken);
'''
    install_replacement = '''        progress("Installing Endweave…");
        await McsvEndweaveInstaller.InstallAsync(
            api,
            endweaveWheel,
            progress,
            cancellationToken);

        progress("Installing Endstone plugin…");
        await InstallPluginAsync(api, cancellationToken);
'''
    text = replace_once(
        text,
        install_anchor,
        install_replacement,
        "Endweave before VoiceCraft plugin",
    )

    item_mic_anchor = '''        progress("Installing Item Mic add-on…");
        await InstallItemMicAsync(api, cancellationToken);

        progress("Enabling add-on in active world…");
'''
    item_mic_replacement = '''        progress("Installing Item Mic add-on…");
        await InstallItemMicAsync(api, cancellationToken);
        await McsvInstallVerifier.VerifyItemMicFilesAsync(
            api,
            progress,
            cancellationToken);

        progress("Enabling add-on in active world…");
'''
    text = replace_once(
        text,
        item_mic_anchor,
        item_mic_replacement,
        "verify Item Mic files after install",
    )

    world_anchor = '''        progress("Enabling add-on in active world…");
        await EnableItemMicForActiveWorldAsync(api, cancellationToken);

        // Restart only after every required installation step has succeeded.
'''
    world_replacement = '''        progress("Enabling add-on in active world…");
        await EnableItemMicForActiveWorldAsync(api, cancellationToken);
        await McsvInstallVerifier.VerifyConfigAndActiveWorldAsync(
            api,
            serverId,
            progress,
            cancellationToken);

        // Restart only after every required installation step has succeeded.
'''
    text = replace_once(
        text,
        world_anchor,
        world_replacement,
        "verify config and world before restart",
    )

    restart_anchor = '''        var running = false;
        if (allowedTools.Contains("server_overview"))
        {
            progress("Waiting for MCSV server…");
            running = await WaitUntilRunningAsync(api, cancellationToken);
        }

        progress(running ? "Installation complete — server online" : "Installation complete — restart requested");
'''
    restart_replacement = '''        progress("Waiting for MCSV server to return online…");
        var running = await WaitUntilRunningAsync(api, cancellationToken);
        if (!running)
            throw new McsvApiException(
                "MCSV server did not return to Running state within the verification window after restart.");

        progress("Server is online — checking startup logs…");
        await McsvStartupVerifier.VerifyAsync(
            api,
            progress,
            cancellationToken);
        progress("Ready — Endweave + VoiceCraft online");
'''
    text = replace_once(
        text,
        restart_anchor,
        restart_replacement,
        "require successful restart and startup log verification",
    )

    installer.write_text(text, encoding="utf-8")

    final = installer.read_text(encoding="utf-8")
    required = [
        MARKER,
        '"server_overview"',
        '"logs_startup"',
        '"backups_create"',
        "voicecraft-endweave-v2-preinstall",
        "McsvEndweaveSupport.ValidatePreflightAsync",
        "McsvEndweaveSupport.DetectEnvironmentAsync",
        "McsvPythonEnvironmentValidator.ValidateAsync",
        "McsvEndweaveCatalog.SelectWheel",
        "McsvEndweaveInstaller.InstallAsync",
        "McsvInstallVerifier.VerifyItemMicFilesAsync",
        "McsvInstallVerifier.VerifyConfigAndActiveWorldAsync",
        "McsvStartupVerifier.VerifyAsync",
        "Ready — Endweave + VoiceCraft online",
        'progress("Installing Endstone plugin…")',
    ]
    missing = [value for value in required if value not in final]
    if missing:
        raise RuntimeError(f"MCSV Endweave V2 validation failed: {missing}")

    backup_pos = final.index("voicecraft-endweave-v2-preinstall")
    endweave_pos = final.index("McsvEndweaveInstaller.InstallAsync")
    voicecraft_pos = final.index("await InstallPluginAsync")
    if not (backup_pos < endweave_pos < voicecraft_pos):
        raise RuntimeError("Required order is backup -> Endweave -> VoiceCraft plugin")

    verify_pos = final.index("McsvInstallVerifier.VerifyConfigAndActiveWorldAsync")
    restart_pos = final.index('new { action = "restart" }')
    if verify_pos >= restart_pos:
        raise RuntimeError("Config/world verification must complete before restart")

    wait_pos = final.index("await WaitUntilRunningAsync")
    startup_pos = final.index("McsvStartupVerifier.VerifyAsync")
    if wait_pos >= startup_pos:
        raise RuntimeError("Server must be confirmed Running before startup log verification")

    print(f"Applied MCSV Endweave V2 orchestration to {installer}")


if __name__ == "__main__":
    main()
