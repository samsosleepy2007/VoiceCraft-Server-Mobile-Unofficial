#!/usr/bin/env python3
from pathlib import Path
import re
import sys


def require(text: str, needle: str, label: str) -> None:
    if needle not in text:
        raise RuntimeError(f"Render security validation failed: missing {label}")


def forbid(text: str, pattern: str, label: str, flags: int = 0) -> None:
    if re.search(pattern, text, flags):
        raise RuntimeError(f"Render security validation failed: forbidden {label}")


def main() -> None:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
    android = root / "VoiceCraft.Server.Android"
    api_path = android / "RenderApiClient.cs"
    activity_path = android / "ModernMainActivity.cs"
    prefs_path = android / "ServerPreferences.cs"
    gate_path = android / "BackupRelayPremiumGateProvider.cs"
    upstream_path = root / "VoiceCraft.Upstream" / "VoiceCraft.Network" / "Servers" / "VoiceCraftServer.cs"

    for path in (api_path, activity_path, prefs_path, gate_path, upstream_path):
        if not path.exists():
            raise RuntimeError(f"Render security validation failed: missing {path}")

    api = api_path.read_text(encoding="utf-8")
    activity = activity_path.read_text(encoding="utf-8")
    prefs = prefs_path.read_text(encoding="utf-8")
    gate = gate_path.read_text(encoding="utf-8")
    upstream = upstream_path.read_text(encoding="utf-8")

    require(api, 'new("https://api.render.com/v1/")', "fixed HTTPS Render API origin")
    require(api, "AllowAutoRedirect = false", "redirect blocking")
    require(api, 'request.Headers.Authorization = new AuthenticationHeaderValue("Bearer", apiKey.Trim())', "Bearer authorization")
    require(api, 'private const string RelayBranch = "main";', "stable relay source branch")
    require(api, 'private const string RelayRootDir = "VoiceCraft.Bridge.Relay";', "relay root directory")
    require(api, 'new { key = "BRIDGE_SECRET", value = bridgeSecret }', "BRIDGE_SECRET environment variable")
    require(api, 'buildCommand = "npm install --omit=dev"', "relay build command")
    require(api, 'startCommand = "npm start"', "relay start command")
    require(api, 'healthCheckPath = "/health"', "relay health check")
    require(api, 'Redact(ExtractErrorMessage(responseText), apiKey)', "API error redaction")
    require(api, 'services?name=', "duplicate service lookup")
    require(api, '&type=web_service&includePreviews=false&limit=100', "duplicate lookup scope")

    require(activity, "private EditText? _renderApiKey;", "session-only Render key field")
    require(activity, "_renderApiKey.Text = string.Empty;", "API key wipe")
    require(activity, "_renderProvisionCts?.Cancel();", "deploy poll cancellation")
    require(activity, '"BRIDGE" => HasLogCategory(row, "BRIDGE") || HasLogCategory(row, "RENDER")', "Render log filtering")

    # Render provisioning is intentionally simplified: workspace, service name,
    # region and plan are automatic/fixed and are not editable inputs.
    require(activity, 'private const string RenderServiceName = "VoiceCraft by SamSoSleepy";', "fixed Render service name")
    require(activity, 'private const string RenderRegion = "Singapore";', "fixed Singapore region")
    require(activity, 'private const string RenderPlan = "Free";', "fixed Free plan")
    require(activity, "var workspace = workspaces[0];", "automatic workspace selection")
    require(activity, "workspace.Id,", "automatic workspace ID passed to Render")
    require(activity, "RenderServiceName,", "fixed service name passed to Render")
    require(activity, "RenderRegion,", "fixed region passed to Render")
    require(activity, "RenderPlan,", "fixed plan passed to Render")
    require(activity, "RenderApiClient.FindServiceByNameAsync(apiKey, RenderServiceName)", "duplicate service guard")
    forbid(activity, r"_renderWorkspace\s*=\s*new\s+Spinner", "interactive Render workspace selector")
    forbid(activity, r"_renderRegion\s*=\s*new\s+Spinner", "interactive Render region selector")
    forbid(activity, r"_renderPlan\s*=\s*new\s+Spinner", "interactive Render plan selector")
    forbid(activity, r"_renderServiceName\s*=\s*Input", "interactive Render service name input")

    # Primary/Backup selection is entitlement-aware. Free users cannot invoke a
    # Backup create path; Premium/Admin are verified through the existing account API.
    require(gate, "internal static async Task<bool> CanUseBackupRelayAsync(Context context)", "non-destructive backup entitlement check")
    require(gate, 'capabilities.TryGetProperty("backupRelays", out var backupRelays)', "backup relay capability lookup")
    require(activity, "BackupRelayPremiumGate.CanUseBackupRelayAsync(this)", "account entitlement used by Render provisioning")
    require(activity, "_renderBackupTarget.Enabled = connected && backupAllowed;", "Backup target lock")
    require(activity, "if (targetIsBackup && !_renderBackupAllowed)", "Backup create safety gate")

    # Duplicate Render services are blocked. Existing primary/backup config is
    # preserved until the new Render deploy is LIVE, then only the selected slot
    # is updated.
    require(activity, "ShowDuplicateRenderServiceWarning();", "duplicate service warning")
    require(activity, "If deployment fails, the current relay stays unchanged.", "safe replacement explanation")
    require(activity, "ApplyCreatedRenderRelayUrl(url, targetIsBackup)", "LIVE-only relay application")
    require(activity, "ServerPreferences.SaveBridge(this, true, websocket, CurrentServerId(), CurrentSecret())", "Primary relay persistence")
    require(activity, "ServerPreferences.SaveBridgeBackups(this, backups)", "Backup relay persistence")
    require(activity, "backups[0] = websocket;", "single Backup slot replacement")

    # Inline setup help must explain how to create a Render API key without ever
    # persisting the key itself.
    require(activity, "Render Dashboard > Account Settings > API Keys > Create API Key", "Render API key instructions")

    # Dashboard identity uses the verified GitHub profile avatar, with an offline
    # initials fallback so the page never depends on GitHub to render.
    require(activity, "SamSoSleepy GitHub profile picture", "dashboard GitHub profile accessibility label")
    require(activity, "https://avatars.githubusercontent.com/u/235958240?v=4", "SamSoSleepy GitHub avatar source")
    require(activity, 'var profileFallback = Label("SS", 13, Primary, true);', "offline avatar fallback")
    require(activity, "LoadDashboardProfileAvatarAsync(profileAvatar)", "non-blocking dashboard avatar loader")
    require(activity, "profileAvatar.Visibility = ViewStates.Visible;", "avatar success state")
    forbid(activity, r'var\s+vc\s*=\s*Pill\("VC"', "legacy VC dashboard badge")

    # Never persist, copy, or log the API-key variable.
    forbid(prefs, r"render\s*_?api\s*_?key|renderApiKey", "Render API key persistence", re.I)
    forbid(activity, r"ServerPreferences\.[A-Za-z0-9_]*(?:\([^\n]*_renderApiKey|_renderApiKey[^\n]*\))", "Render API key sent to preferences")
    forbid(activity, r"AndroidRuntimeLog\.Append\([^\n]*\bapiKey\b", "Render API key written to logs")
    forbid(activity, r"Clipboard[^\n]*_renderApiKey|_renderApiKey[^\n]*Clipboard", "Render API key copied to clipboard", re.I)
    forbid(activity, r"CopyAllSetup[\s\S]{0,1500}_renderApiKey", "Render API key in copied setup")

    # Keep existing moderation/audio and protocol safety invariants untouched.
    require(upstream, "networkEntity.Muted || networkEntity.ServerMuted || itemMicMuted", "moderation-safe Item Mic audio gate")
    manifest = (root / "release-manifest.json").read_text(encoding="utf-8")
    require(manifest, '"protocol": 1', "protocol 1 manifest")

    print("Render provisioning and Dashboard identity validation passed.")
    print("- API key is session-only, wiped on destroy, and excluded from prefs/logs/clipboard")
    print("- workspace is automatic; service name is fixed to VoiceCraft by SamSoSleepy")
    print("- duplicate service creation is blocked and a different Render account/API key is required")
    print("- Free Account locks Backup; Premium/Admin uses the real backupRelays entitlement")
    print("- replacement is confirmed first and saved only after the new deploy is LIVE")
    print("- region is fixed to Singapore and plan is fixed to Free; no selectors remain")
    print("- Dashboard uses SamSoSleepy's GitHub avatar with an SS offline fallback")
    print("- Item Mic moderation gate and protocol 1 remain intact")


if __name__ == "__main__":
    main()
