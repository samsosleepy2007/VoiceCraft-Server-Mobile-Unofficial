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

    installer.write_text(text, encoding="utf-8")

    final = installer.read_text(encoding="utf-8")
    required = [
        MARKER,
        "McsvEndweaveSupport.ValidatePreflightAsync",
        "McsvEndweaveSupport.DetectEnvironmentAsync",
        "McsvPythonEnvironmentValidator.ValidateAsync",
        "McsvEndweaveCatalog.SelectWheel",
        "McsvEndweaveInstaller.InstallAsync",
        'progress("Installing Endstone plugin…")',
    ]
    missing = [value for value in required if value not in final]
    if missing:
        raise RuntimeError(f"MCSV Endweave V2 validation failed: {missing}")

    endweave_pos = final.index("McsvEndweaveInstaller.InstallAsync")
    voicecraft_pos = final.index("await InstallPluginAsync")
    if endweave_pos >= voicecraft_pos:
        raise RuntimeError("Endweave must be staged before the VoiceCraft Endstone plugin")

    print(f"Applied MCSV Endweave V2 orchestration to {installer}")


if __name__ == "__main__":
    main()
