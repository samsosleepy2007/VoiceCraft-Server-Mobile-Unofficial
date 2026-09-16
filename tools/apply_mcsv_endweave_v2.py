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

    installer.write_text(text, encoding="utf-8")

    final = installer.read_text(encoding="utf-8")
    required = [
        MARKER,
        "McsvEndweaveSupport.ValidatePreflightAsync",
        "McsvEndweaveSupport.DetectEnvironmentAsync",
        "McsvPythonEnvironmentValidator.ValidateAsync",
        "McsvEndweaveCatalog.SelectWheel",
        "McsvEndweaveInstaller.InstallAsync",
        "McsvInstallVerifier.VerifyItemMicFilesAsync",
        "McsvInstallVerifier.VerifyConfigAndActiveWorldAsync",
        'progress("Installing Endstone plugin…")',
    ]
    missing = [value for value in required if value not in final]
    if missing:
        raise RuntimeError(f"MCSV Endweave V2 validation failed: {missing}")

    endweave_pos = final.index("McsvEndweaveInstaller.InstallAsync")
    voicecraft_pos = final.index("await InstallPluginAsync")
    if endweave_pos >= voicecraft_pos:
        raise RuntimeError("Endweave must be staged before the VoiceCraft Endstone plugin")

    verify_pos = final.index("McsvInstallVerifier.VerifyConfigAndActiveWorldAsync")
    restart_pos = final.index('new { action = "restart" }')
    if verify_pos >= restart_pos:
        raise RuntimeError("Config/world verification must complete before restart")

    print(f"Applied MCSV Endweave V2 orchestration to {installer}")


if __name__ == "__main__":
    main()
