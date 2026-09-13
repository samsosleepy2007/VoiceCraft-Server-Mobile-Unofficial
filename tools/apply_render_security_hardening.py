#!/usr/bin/env python3
from pathlib import Path
import sys


def replace_required(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise RuntimeError(f"Render security hardening failed: {label}")
    return text.replace(old, new, 1)


def main() -> None:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
    path = root / "VoiceCraft.Server.Android" / "ModernMainActivity.cs"
    text = path.read_text(encoding="utf-8")

    # Render provisioning belongs with Bridge filtering in Runtime Logs.
    text = replace_required(
        text,
        '        "BRIDGE" => HasLogCategory(row, "BRIDGE"),\n',
        '        "BRIDGE" => HasLogCategory(row, "BRIDGE") || HasLogCategory(row, "RENDER"),\n',
        "include Render provisioning in Bridge log filter",
    )

    # A completed Render deploy is a successful connectivity/provisioning state.
    text = replace_required(
        text,
        '''        if (value.Contains(" connected", StringComparison.OrdinalIgnoreCase)\n            || value.Contains("online", StringComparison.OrdinalIgnoreCase)\n            || value.Contains("ready", StringComparison.OrdinalIgnoreCase))\n            return Green;\n''',
        '''        if (value.Contains(" connected", StringComparison.OrdinalIgnoreCase)\n            || value.Contains("online", StringComparison.OrdinalIgnoreCase)\n            || value.Contains("ready", StringComparison.OrdinalIgnoreCase)\n            || value.Contains("deploy live", StringComparison.OrdinalIgnoreCase))\n            return Green;\n''',
        "classify live Render deploy as green",
    )

    # Android.OS also defines OperationCanceledException. Qualify the System type
    # used by Task/CancellationToken so the generated activity always compiles.
    text = replace_required(
        text,
        "        catch (OperationCanceledException)\n",
        "        catch (System.OperationCanceledException)\n",
        "qualify Render deploy cancellation exception",
    )

    # Render API keys remain session-only. Cancel deploy polling and wipe the
    # visible field when the Activity is destroyed. Nothing is written to prefs.
    destroy = '''    protected override void OnDestroy()\n    {\n        if (_handler != null && _refreshRunnable != null)\n'''
    hardened_destroy = '''    protected override void OnDestroy()\n    {\n        _renderProvisionCts?.Cancel();\n        _renderProvisionCts?.Dispose();\n        _renderProvisionCts = null;\n        if (_renderApiKey != null)\n            _renderApiKey.Text = string.Empty;\n        _renderWorkspaceOptions = Array.Empty<RenderWorkspaceOption>();\n        _renderCreatedServiceId = string.Empty;\n        _renderCreatedServiceUrl = string.Empty;\n\n        if (_handler != null && _refreshRunnable != null)\n'''
    text = replace_required(text, destroy, hardened_destroy, "wipe Render provisioning session on destroy")

    path.write_text(text, encoding="utf-8")
    print(f"Applied Render provisioning security hardening to {path}")
    print("- Render API key cleared and polling cancelled on Activity destroy")
    print("- Render provisioning logs grouped with Bridge")
    print("- live deploy state classified green")
    print("- Render deploy cancellation exception qualified for Android build")


if __name__ == "__main__":
    main()
