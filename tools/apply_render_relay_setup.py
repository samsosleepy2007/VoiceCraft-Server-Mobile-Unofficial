#!/usr/bin/env python3
from pathlib import Path
import sys


def replace_required(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise RuntimeError(f"Render setup UI patch failed: {label}")
    return text.replace(old, new, 1)


def main() -> None:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
    path = root / "VoiceCraft.Server.Android" / "ModernMainActivity.cs"
    text = path.read_text(encoding="utf-8")

    fields_anchor = "    private TextView? _configPreview;\n"
    fields = fields_anchor + '''    private const string RenderWorkspaceName = "VoiceCraft By SamSoSleepy";
    private const string RenderRegion = "Singapore";
    private const string RenderPlan = "Free";
    private EditText? _renderApiKey;
    private EditText? _renderServiceName;
    private TextView? _renderProvisionStatus;
    private Button? _renderConnect;
    private Button? _renderCreate;
    private IReadOnlyList<RenderWorkspaceOption> _renderWorkspaceOptions = Array.Empty<RenderWorkspaceOption>();
    private string _renderCreatedServiceId = string.Empty;
    private string _renderCreatedServiceUrl = string.Empty;
    private CancellationTokenSource? _renderProvisionCts;
'''
    text = replace_required(text, fields_anchor, fields, "Render UI fields")

    bridge_anchor = '''        body.AddView(relay, CardLayout());

        var identity = Card();
'''
    render_card = '''        body.AddView(relay, CardLayout());

        var renderCreate = Card();
        renderCreate.AddView(SectionTitle(T("สร้าง Render Relay", "Create Render Relay"), Primary));
        renderCreate.AddView(Label(
            T("สร้าง Web Service สำหรับ VoiceCraft Relay จากในแอป โดย API Key ใช้เฉพาะ session นี้และจะไม่ถูกบันทึก", "Create the VoiceCraft Relay Web Service from the app. The API key is used only for this session and is never saved."),
            11,
            Muted));
        renderCreate.AddView(Label(
            T("Workspace: VoiceCraft By SamSoSleepy • Region: Singapore • Plan: Free", "Workspace: VoiceCraft By SamSoSleepy • Region: Singapore • Plan: Free"),
            10,
            Muted), Top(Dp(6)));

        renderCreate.AddView(InputLabel("Render API Key"));
        _renderApiKey = Input(string.Empty, InputTypes.ClassText | InputTypes.TextVariationPassword);
        _renderApiKey.Hint = "rnd_...";
        renderCreate.AddView(_renderApiKey);

        _renderConnect = MakeButton(T("เชื่อมต่อ Render", "CONNECT TO RENDER"), primary: true);
        WireButton(_renderConnect, ConnectRenderAccount);
        var renderConnectRow = ButtonRow();
        renderConnectRow.AddView(_renderConnect, new LinearLayout.LayoutParams(0, Dp(48), 1f) { LeftMargin = Dp(3), RightMargin = Dp(3) });
        renderCreate.AddView(renderConnectRow);

        renderCreate.AddView(InputLabel(T("ชื่อ Service", "Service Name")));
        _renderServiceName = Input("voicecraft-relay-" + Guid.NewGuid().ToString("N")[..6], InputTypes.ClassText);
        _renderServiceName.Hint = "voicecraft-relay-name";
        renderCreate.AddView(_renderServiceName);

        _renderCreate = MakeButton(T("สร้าง Web Service", "CREATE WEB SERVICE"), primary: true);
        WireButton(_renderCreate, CreateRenderRelayService);
        _renderCreate.Enabled = false;
        _renderCreate.Alpha = 0.45f;
        var renderCreateRow = ButtonRow();
        renderCreateRow.AddView(_renderCreate, new LinearLayout.LayoutParams(0, Dp(48), 1f) { LeftMargin = Dp(3), RightMargin = Dp(3) });
        renderCreate.AddView(renderCreateRow);

        _renderProvisionStatus = Label(
            T("ใส่ API Key แล้วกดเชื่อมต่อ ระบบจะเลือก Workspace VoiceCraft By SamSoSleepy ให้อัตโนมัติ", "Enter an API key and connect. VoiceCraft By SamSoSleepy will be selected automatically."),
            10,
            Muted);
        renderCreate.AddView(_renderProvisionStatus, Top(Dp(8)));
        body.AddView(renderCreate, CardLayout());

        var identity = Card();
'''
    text = replace_required(text, bridge_anchor, render_card, "Render provisioning card")

    methods_anchor = "    private void ShowOpenSourceLegal()\n"
    if methods_anchor not in text:
        methods_anchor = "    private void ShowInformation()\n"

    methods = r'''    private void SetRenderProvisionStatus(string text, Color color)
    {
        if (_renderProvisionStatus == null)
            return;
        _renderProvisionStatus.Text = text;
        _renderProvisionStatus.SetTextColor(color);
    }

    private void SetRenderCreateEnabled(bool enabled)
    {
        if (_renderCreate == null)
            return;
        _renderCreate.Enabled = enabled;
        _renderCreate.Alpha = enabled ? 1f : 0.45f;
    }

    private async void ConnectRenderAccount()
    {
        var apiKey = _renderApiKey?.Text?.Trim() ?? string.Empty;
        if (string.IsNullOrWhiteSpace(apiKey))
        {
            SetRenderProvisionStatus(T("กรอก Render API Key ก่อน", "Enter a Render API key first"), Red);
            return;
        }

        if (_renderConnect != null)
        {
            _renderConnect.Enabled = false;
            _renderConnect.Alpha = 0.55f;
        }
        SetRenderCreateEnabled(false);
        SetRenderProvisionStatus(T("กำลังตรวจสอบบัญชี Render และค้นหา Workspace…", "Checking your Render account and locating the workspace…"), Amber);

        try
        {
            var workspaces = await RenderApiClient.ListWorkspacesAsync(apiKey);
            var workspace = workspaces.FirstOrDefault(item =>
                string.Equals(item.Name?.Trim(), RenderWorkspaceName, StringComparison.OrdinalIgnoreCase));

            if (workspace == null)
            {
                _renderWorkspaceOptions = Array.Empty<RenderWorkspaceOption>();
                SetRenderCreateEnabled(false);
                SetRenderProvisionStatus(
                    T("ไม่พบ Workspace 'VoiceCraft By SamSoSleepy' ในบัญชี Render นี้", "Workspace 'VoiceCraft By SamSoSleepy' was not found in this Render account."),
                    Red);
                AndroidRuntimeLog.Append("RENDER", $"Render account connected but target workspace was not found; workspaces={workspaces.Count}; API key hidden");
                return;
            }

            _renderWorkspaceOptions = new[] { workspace };
            SetRenderCreateEnabled(true);
            SetRenderProvisionStatus(
                T("เชื่อมต่อ Render สำเร็จ • ใช้ Workspace VoiceCraft By SamSoSleepy", "Connected to Render • using VoiceCraft By SamSoSleepy"),
                Green);
            AndroidRuntimeLog.Append("RENDER", $"Render account connected; target workspace selected automatically; workspaces={workspaces.Count}; API key hidden");
        }
        catch (RenderApiException ex)
        {
            _renderWorkspaceOptions = Array.Empty<RenderWorkspaceOption>();
            SetRenderProvisionStatus(ex.Message, Red);
            AndroidRuntimeLog.Append("RENDER", $"Render account connection failed: {ex.Message}; API key hidden");
        }
        catch (Exception ex)
        {
            _renderWorkspaceOptions = Array.Empty<RenderWorkspaceOption>();
            SetRenderProvisionStatus(T("เชื่อมต่อ Render ไม่สำเร็จ", "Unable to connect to Render"), Red);
            AndroidRuntimeLog.Append("RENDER", $"Render account connection failed: {ex.GetType().Name}; API key hidden");
        }
        finally
        {
            if (_renderConnect != null)
            {
                _renderConnect.Enabled = true;
                _renderConnect.Alpha = 1f;
            }
        }
    }

    private async void CreateRenderRelayService()
    {
        var apiKey = _renderApiKey?.Text?.Trim() ?? string.Empty;
        if (string.IsNullOrWhiteSpace(apiKey))
        {
            SetRenderProvisionStatus(T("Render API Key หมดจาก session แล้ว กรุณาเชื่อมต่อใหม่", "Render API key is no longer available. Connect again."), Red);
            return;
        }

        if (_renderWorkspaceOptions.Count != 1)
        {
            SetRenderProvisionStatus(
                T("ยังไม่พบ Workspace VoiceCraft By SamSoSleepy กรุณาเชื่อมต่อ Render ใหม่", "VoiceCraft By SamSoSleepy is not available. Connect to Render again."),
                Red);
            return;
        }

        var serviceName = _renderServiceName?.Text?.Trim() ?? string.Empty;
        var secret = _bridgeSecret?.Text?.Trim() ?? string.Empty;
        if (secret.Length < 16)
        {
            secret = Convert.ToHexString(RandomNumberGenerator.GetBytes(24)).ToLowerInvariant();
            if (_bridgeSecret != null)
                _bridgeSecret.Text = secret;
            RefreshBridgePreview();
        }

        _renderProvisionCts?.Cancel();
        _renderProvisionCts?.Dispose();
        _renderProvisionCts = new CancellationTokenSource();
        var token = _renderProvisionCts.Token;

        SetRenderCreateEnabled(false);
        if (_renderConnect != null)
            _renderConnect.Enabled = false;
        SetRenderProvisionStatus(T("กำลังสร้าง Render Web Service…", "Creating Render Web Service…"), Amber);

        try
        {
            var workspace = _renderWorkspaceOptions[0];
            var created = await RenderApiClient.CreateRelayServiceAsync(
                apiKey,
                workspace.Id,
                serviceName,
                RenderRegion,
                RenderPlan,
                secret,
                token);
            _renderCreatedServiceId = created.Id;
            _renderCreatedServiceUrl = created.Url;
            AndroidRuntimeLog.Append("RENDER", $"Relay service created id={created.Id} name={created.Name}; workspace fixed; region=Singapore; plan=free; Bridge Secret hidden");
            await MonitorRenderRelayDeployAsync(apiKey, created, token);
        }
        catch (OperationCanceledException)
        {
            SetRenderProvisionStatus(T("หยุดติดตามการ Deploy แล้ว", "Deploy monitoring stopped"), Amber);
        }
        catch (RenderApiException ex)
        {
            SetRenderCreateEnabled(true);
            SetRenderProvisionStatus(ex.Message, Red);
            AndroidRuntimeLog.Append("RENDER", $"Relay provisioning failed: {ex.Message}; secrets hidden");
        }
        catch (Exception ex)
        {
            SetRenderCreateEnabled(true);
            SetRenderProvisionStatus(T("สร้าง Render Web Service ไม่สำเร็จ", "Unable to create Render Web Service"), Red);
            AndroidRuntimeLog.Append("RENDER", $"Relay provisioning failed: {ex.GetType().Name}; secrets hidden");
        }
        finally
        {
            if (_renderConnect != null)
                _renderConnect.Enabled = true;
        }
    }

    private async Task MonitorRenderRelayDeployAsync(string apiKey, RenderCreatedService created, CancellationToken token)
    {
        SetRenderProvisionStatus(T("สร้าง Service แล้ว • กำลัง Deploy…", "Service created • deploying…"), Amber);
        for (var attempt = 0; attempt < 60; attempt++)
        {
            token.ThrowIfCancellationRequested();
            var deploy = await RenderApiClient.GetLatestDeployAsync(apiKey, created.Id, token);
            var status = (deploy.Status ?? string.Empty).Trim().ToLowerInvariant();

            if (IsRenderDeploySuccessful(status))
            {
                var service = await RenderApiClient.GetServiceAsync(apiKey, created.Id, token);
                var url = string.IsNullOrWhiteSpace(service.Url) ? created.Url : service.Url;
                if (string.IsNullOrWhiteSpace(url))
                    throw new RenderApiException("Render deploy is live but no public service URL was returned.");

                ApplyCreatedRenderRelayUrl(url);
                SetRenderProvisionStatus(
                    T($"Render Relay พร้อมใช้งาน • {url}", $"Render Relay is LIVE • {url}"),
                    Green);
                AndroidRuntimeLog.Append("RENDER", $"Relay deploy live service={created.Id}; URL configured automatically; secrets hidden");
                if (_renderApiKey != null)
                    _renderApiKey.Text = string.Empty;
                return;
            }

            if (IsRenderDeployFailed(status))
            {
                SetRenderCreateEnabled(true);
                SetRenderProvisionStatus(
                    T($"Render Deploy ล้มเหลว • {status}", $"Render deploy failed • {status}"),
                    Red);
                AndroidRuntimeLog.Append("RENDER", $"Relay deploy failed service={created.Id} status={status}; secrets hidden");
                return;
            }

            var displayStatus = string.IsNullOrWhiteSpace(status) ? "waiting" : status;
            SetRenderProvisionStatus(
                T($"กำลัง Deploy… • {displayStatus}", $"Deploying… • {displayStatus}"),
                Amber);
            await Task.Delay(TimeSpan.FromSeconds(5), token);
        }

        SetRenderCreateEnabled(true);
        SetRenderProvisionStatus(
            T("Render ยัง Deploy ไม่เสร็จภายในเวลาที่กำหนด ตรวจสอบต่อใน Render Dashboard", "Render is still deploying. Check the Render Dashboard for progress."),
            Amber);
        AndroidRuntimeLog.Append("RENDER", $"Relay deploy monitoring timed out service={created.Id}; secrets hidden");
    }

    private static bool IsRenderDeploySuccessful(string status) =>
        status is "live" or "succeeded" or "successful" or "deployed";

    private static bool IsRenderDeployFailed(string status) =>
        status.Contains("failed", StringComparison.OrdinalIgnoreCase)
        || status.Contains("canceled", StringComparison.OrdinalIgnoreCase)
        || status.Contains("cancelled", StringComparison.OrdinalIgnoreCase)
        || status.Contains("deactivated", StringComparison.OrdinalIgnoreCase);

    private void ApplyCreatedRenderRelayUrl(string serviceUrl)
    {
        if (!Uri.TryCreate(serviceUrl, UriKind.Absolute, out var uri)
            || !uri.Scheme.Equals("https", StringComparison.OrdinalIgnoreCase)
            || string.IsNullOrWhiteSpace(uri.Host))
            throw new RenderApiException("Render returned an invalid public service URL.");

        var cleanUrl = uri.GetLeftPart(UriPartial.Authority).TrimEnd('/');
        _renderCreatedServiceUrl = cleanUrl;
        if (_renderUrl != null)
            _renderUrl.Text = cleanUrl;
        UpdateWebSocketFromRenderUrl();

        var websocket = MakeWebSocketUrl(cleanUrl);
        if (!IsBridgeUrlValid(websocket))
            throw new RenderApiException("Unable to generate the Render Relay WebSocket URL.");
        ServerPreferences.SaveBridge(this, true, websocket, CurrentServerId(), CurrentSecret());
        RefreshBridgePreview();
    }

'''
    text = replace_required(text, methods_anchor, methods + methods_anchor, "Render provisioning methods")

    path.write_text(text, encoding="utf-8")
    final = path.read_text(encoding="utf-8")
    required = [
        'private const string RenderWorkspaceName = "VoiceCraft By SamSoSleepy";',
        'private const string RenderRegion = "Singapore";',
        'private const string RenderPlan = "Free";',
        "RenderApiClient.CreateRelayServiceAsync(",
        "RenderApiClient.GetLatestDeployAsync(",
        "RenderApiClient.GetServiceAsync(",
        "ApplyCreatedRenderRelayUrl(url)",
        "ServerPreferences.SaveBridge(this, true, websocket",
    ]
    missing = [value for value in required if value not in final]
    if missing:
        raise RuntimeError(f"Render setup UI validation failed: {missing}")

    forbidden = [
        "_renderWorkspace = new Spinner",
        "_renderRegion = new Spinner",
        "_renderPlan = new Spinner",
    ]
    present = [value for value in forbidden if value in final]
    if present:
        raise RuntimeError(f"Render fixed defaults validation failed: interactive selectors still present: {present}")

    print(f"Applied Render Relay provisioning UI to {path}")
    print("- target workspace fixed to VoiceCraft By SamSoSleepy and resolved automatically by ID")
    print("- region fixed to Singapore and plan fixed to Free")
    print("- creates the web service and generated Bridge Secret")
    print("- follows the initial deploy until live/failed")
    print("- auto-configures https://...onrender.com -> wss://.../bridge")
    print("- clears the API key field after a successful live deploy")


if __name__ == "__main__":
    main()
