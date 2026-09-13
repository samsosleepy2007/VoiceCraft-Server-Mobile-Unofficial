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
    fields = fields_anchor + '''    private const string RenderServiceName = "VoiceCraft by SamSoSleepy";
    private const string RenderRegion = "Singapore";
    private const string RenderPlan = "Free";
    private EditText? _renderApiKey;
    private TextView? _renderProvisionStatus;
    private Button? _renderConnect;
    private Button? _renderPrimaryTarget;
    private Button? _renderBackupTarget;
    private Button? _renderCreate;
    private IReadOnlyList<RenderWorkspaceOption> _renderWorkspaceOptions = Array.Empty<RenderWorkspaceOption>();
    private bool _renderBackupAllowed;
    private bool _renderTargetIsBackup;
    private bool _renderTargetSelected;
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
            T("สร้าง VoiceCraft Render Relay จากในแอป โดย Render API Key ใช้เฉพาะ session นี้และจะไม่ถูกบันทึก", "Create a VoiceCraft Render Relay from the app. Your Render API key is session-only and is never saved."),
            11,
            Muted));
        renderCreate.AddView(Label(
            T("วิธีรับ API Key: เปิด Render Dashboard > Account Settings > API Keys > Create API Key แล้วคัดลอก Key มาใส่ด้านล่าง", "How to get an API key: Render Dashboard > Account Settings > API Keys > Create API Key, then paste the key below."),
            10,
            Muted), Top(Dp(6)));
        renderCreate.AddView(Label(
            T("Service: VoiceCraft by SamSoSleepy • Workspace: อัตโนมัติ • Region: Singapore • Plan: Free", "Service: VoiceCraft by SamSoSleepy • Workspace: automatic • Region: Singapore • Plan: Free"),
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

        renderCreate.AddView(InputLabel(T("สร้าง Relay ให้", "Create Relay For")));
        var renderTargetRow = ButtonRow();
        _renderPrimaryTarget = MakeButton(T("ตัวหลัก", "PRIMARY RELAY"), primary: true);
        WireButton(_renderPrimaryTarget, () => ChooseRenderTarget(false));
        _renderBackupTarget = MakeButton(T("ตัวสำรอง • ล็อก", "BACKUP RELAY • LOCKED"));
        WireButton(_renderBackupTarget, () => ChooseRenderTarget(true));
        renderTargetRow.AddView(_renderPrimaryTarget, new LinearLayout.LayoutParams(0, Dp(48), 1f) { LeftMargin = Dp(3), RightMargin = Dp(3) });
        renderTargetRow.AddView(_renderBackupTarget, new LinearLayout.LayoutParams(0, Dp(48), 1f) { LeftMargin = Dp(3), RightMargin = Dp(3) });
        renderCreate.AddView(renderTargetRow);

        _renderCreate = MakeButton(T("สร้าง Render Relay", "CREATE RENDER RELAY"), primary: true);
        WireButton(_renderCreate, CreateRenderRelayService);
        _renderCreate.Enabled = false;
        _renderCreate.Alpha = 0.45f;
        var renderCreateRow = ButtonRow();
        renderCreateRow.AddView(_renderCreate, new LinearLayout.LayoutParams(0, Dp(48), 1f) { LeftMargin = Dp(3), RightMargin = Dp(3) });
        renderCreate.AddView(renderCreateRow);

        _renderProvisionStatus = Label(
            T("ใส่ API Key แล้วกดเชื่อมต่อ จากนั้นเลือกว่าจะสร้างให้ Primary หรือ Backup", "Enter an API key and connect, then choose Primary or Backup."),
            10,
            Muted);
        renderCreate.AddView(_renderProvisionStatus, Top(Dp(8)));
        body.AddView(renderCreate, CardLayout());

        SetRenderTargetButtons(false, false);

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

    private void SetRenderTargetButtons(bool connected, bool backupAllowed)
    {
        _renderBackupAllowed = backupAllowed;
        _renderTargetSelected = false;
        SetRenderCreateEnabled(false);

        if (_renderPrimaryTarget != null)
        {
            _renderPrimaryTarget.Enabled = connected;
            _renderPrimaryTarget.Alpha = connected ? 1f : 0.45f;
            _renderPrimaryTarget.Text = T("ตัวหลัก", "PRIMARY RELAY");
        }

        if (_renderBackupTarget != null)
        {
            _renderBackupTarget.Enabled = connected && backupAllowed;
            _renderBackupTarget.Alpha = connected && backupAllowed ? 1f : 0.45f;
            _renderBackupTarget.Text = backupAllowed
                ? T("ตัวสำรอง", "BACKUP RELAY")
                : T("ตัวสำรอง • ล็อก", "BACKUP RELAY • LOCKED");
        }

        if (_renderCreate != null)
            _renderCreate.Text = T("สร้าง Render Relay", "CREATE RENDER RELAY");
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
        _renderWorkspaceOptions = Array.Empty<RenderWorkspaceOption>();
        SetRenderTargetButtons(false, false);
        SetRenderProvisionStatus(T("กำลังตรวจสอบบัญชี Render…", "Checking your Render account…"), Amber);

        try
        {
            var workspaces = await RenderApiClient.ListWorkspacesAsync(apiKey);
            var duplicate = await RenderApiClient.FindServiceByNameAsync(apiKey, RenderServiceName);
            if (duplicate != null)
            {
                SetRenderProvisionStatus(
                    T("พบ VoiceCraft Render Relay อยู่แล้วในบัญชี Render นี้", "A VoiceCraft Render Relay already exists in this Render account."),
                    Red);
                AndroidRuntimeLog.Append("RENDER", $"Duplicate relay service blocked id={duplicate.Id}; API key hidden");
                ShowDuplicateRenderServiceWarning();
                if (_renderApiKey != null)
                    _renderApiKey.Text = string.Empty;
                return;
            }

            var workspace = workspaces[0];
            _renderWorkspaceOptions = new[] { workspace };
            var backupAllowed = await BackupRelayPremiumGate.CanUseBackupRelayAsync(this);
            SetRenderTargetButtons(true, backupAllowed);

            SetRenderProvisionStatus(
                backupAllowed
                    ? T("เชื่อมต่อ Render สำเร็จ • เลือก Primary หรือ Backup", "Connected to Render • choose Primary or Backup")
                    : T("เชื่อมต่อ Render สำเร็จ • Free Account ใช้ได้เฉพาะ Primary", "Connected to Render • Free Account can create Primary only"),
                Green);
            AndroidRuntimeLog.Append("RENDER", $"Render account connected; workspace selected automatically; workspaces={workspaces.Count}; backupAllowed={backupAllowed}; API key hidden");
        }
        catch (RenderApiException ex)
        {
            _renderWorkspaceOptions = Array.Empty<RenderWorkspaceOption>();
            SetRenderTargetButtons(false, false);
            SetRenderProvisionStatus(ex.Message, Red);
            AndroidRuntimeLog.Append("RENDER", $"Render account connection failed: {ex.Message}; API key hidden");
        }
        catch (Exception ex)
        {
            _renderWorkspaceOptions = Array.Empty<RenderWorkspaceOption>();
            SetRenderTargetButtons(false, false);
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

    private void ShowDuplicateRenderServiceWarning()
    {
        new AlertDialog.Builder(this)
            .SetTitle(T("มี Render Relay อยู่แล้ว", "Render Relay already exists"))
            .SetMessage(T(
                "บัญชี Render นี้มี Service 'VoiceCraft by SamSoSleepy' อยู่แล้ว จึงไม่สามารถสร้างซ้ำได้ หากต้องการสร้าง Relay เพิ่ม กรุณาเปลี่ยนไปใช้บัญชี Render อื่น แล้วสร้าง API Key ใหม่มาเชื่อมต่อ",
                "This Render account already contains the 'VoiceCraft by SamSoSleepy' service, so another one cannot be created. To create another Relay, use a different Render account and create a new API key."))
            .SetPositiveButton("OK", (_, _) => { })
            .Show();
    }

    private void ChooseRenderTarget(bool backup)
    {
        if (_renderWorkspaceOptions.Count != 1)
        {
            SetRenderProvisionStatus(T("เชื่อมต่อ Render ก่อน", "Connect to Render first"), Red);
            return;
        }

        if (backup && !_renderBackupAllowed)
        {
            SetRenderProvisionStatus(
                T("Backup Relay ใช้ได้เฉพาะ Premium หรือ Admin", "Backup Relay requires Premium or Admin"),
                Red);
            return;
        }

        var current = backup
            ? ServerPreferences.GetBridgeBackupUrls(this).FirstOrDefault() ?? string.Empty
            : ServerPreferences.GetBridgeUrl(this);

        if (!string.IsNullOrWhiteSpace(current))
        {
            var targetName = backup ? T("Backup Relay", "Backup Relay") : T("Primary Relay", "Primary Relay");
            new AlertDialog.Builder(this)
                .SetTitle(T("แทนที่ Render Relay ปัจจุบัน?", "Replace the current Render Relay?"))
                .SetMessage(T(
                    $"มี {targetName} ตั้งค่าอยู่แล้ว หากดำเนินการต่อ Relay ปัจจุบันจะถูกแทนที่ด้วยอันใหม่หลังจาก Service ใหม่ Deploy สำเร็จและ LIVE เท่านั้น หาก Deploy ล้มเหลวค่าเดิมจะยังอยู่",
                    $"A {targetName} is already configured. If you continue, it will be replaced only after the new service deploys successfully and becomes LIVE. If deployment fails, the current relay stays unchanged."))
                .SetPositiveButton(T("ยืนยันการแทนที่", "REPLACE RELAY"), (_, _) => ConfirmRenderTarget(backup))
                .SetNegativeButton(T("ยกเลิก", "CANCEL"), (_, _) => { })
                .Show();
            return;
        }

        ConfirmRenderTarget(backup);
    }

    private void ConfirmRenderTarget(bool backup)
    {
        _renderTargetIsBackup = backup;
        _renderTargetSelected = true;
        SetRenderCreateEnabled(true);

        if (_renderPrimaryTarget != null)
            _renderPrimaryTarget.Text = !backup
                ? T("ตัวหลัก • เลือกแล้ว", "PRIMARY • SELECTED")
                : T("ตัวหลัก", "PRIMARY RELAY");
        if (_renderBackupTarget != null)
            _renderBackupTarget.Text = backup
                ? T("ตัวสำรอง • เลือกแล้ว", "BACKUP • SELECTED")
                : (_renderBackupAllowed ? T("ตัวสำรอง", "BACKUP RELAY") : T("ตัวสำรอง • ล็อก", "BACKUP RELAY • LOCKED"));
        if (_renderCreate != null)
            _renderCreate.Text = backup
                ? T("สร้าง Backup Render Relay", "CREATE BACKUP RELAY")
                : T("สร้าง Primary Render Relay", "CREATE PRIMARY RELAY");

        SetRenderProvisionStatus(
            backup
                ? T("เลือก Backup Relay แล้ว • พร้อมสร้าง", "Backup Relay selected • ready to create")
                : T("เลือก Primary Relay แล้ว • พร้อมสร้าง", "Primary Relay selected • ready to create"),
            Green);
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
            SetRenderProvisionStatus(T("กรุณาเชื่อมต่อ Render ใหม่", "Connect to Render again."), Red);
            return;
        }

        if (!_renderTargetSelected)
        {
            SetRenderProvisionStatus(T("เลือก Primary หรือ Backup ก่อน", "Choose Primary or Backup first"), Red);
            return;
        }

        var targetIsBackup = _renderTargetIsBackup;
        if (targetIsBackup && !_renderBackupAllowed)
        {
            SetRenderProvisionStatus(T("Backup Relay ถูกล็อกสำหรับ Free Account", "Backup Relay is locked for Free Account"), Red);
            return;
        }

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
        if (_renderPrimaryTarget != null)
            _renderPrimaryTarget.Enabled = false;
        if (_renderBackupTarget != null)
            _renderBackupTarget.Enabled = false;
        SetRenderProvisionStatus(T("กำลังสร้าง Render Web Service…", "Creating Render Web Service…"), Amber);

        try
        {
            var workspace = _renderWorkspaceOptions[0];
            var created = await RenderApiClient.CreateRelayServiceAsync(
                apiKey,
                workspace.Id,
                RenderServiceName,
                RenderRegion,
                RenderPlan,
                secret,
                token);
            _renderCreatedServiceId = created.Id;
            _renderCreatedServiceUrl = created.Url;
            AndroidRuntimeLog.Append("RENDER", $"Relay service created id={created.Id} target={(targetIsBackup ? "backup" : "primary")}; workspace automatic; region=Singapore; plan=free; Bridge Secret hidden");
            await MonitorRenderRelayDeployAsync(apiKey, created, targetIsBackup, token);
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
            if (_renderPrimaryTarget != null)
                _renderPrimaryTarget.Enabled = _renderWorkspaceOptions.Count == 1;
            if (_renderBackupTarget != null)
                _renderBackupTarget.Enabled = _renderWorkspaceOptions.Count == 1 && _renderBackupAllowed;
        }
    }

    private async Task MonitorRenderRelayDeployAsync(string apiKey, RenderCreatedService created, bool targetIsBackup, CancellationToken token)
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

                ApplyCreatedRenderRelayUrl(url, targetIsBackup);
                SetRenderProvisionStatus(
                    targetIsBackup
                        ? T($"Backup Render Relay พร้อมใช้งาน • {url}", $"Backup Render Relay is LIVE • {url}")
                        : T($"Primary Render Relay พร้อมใช้งาน • {url}", $"Primary Render Relay is LIVE • {url}"),
                    Green);
                AndroidRuntimeLog.Append("RENDER", $"Relay deploy live service={created.Id}; target={(targetIsBackup ? "backup" : "primary")}; URL configured automatically; secrets hidden");
                if (_renderApiKey != null)
                    _renderApiKey.Text = string.Empty;
                _renderTargetSelected = false;
                SetRenderCreateEnabled(false);
                return;
            }

            if (IsRenderDeployFailed(status))
            {
                SetRenderCreateEnabled(true);
                SetRenderProvisionStatus(
                    T($"Render Deploy ล้มเหลว • {status} • Relay เดิมไม่ได้ถูกเปลี่ยน", $"Render deploy failed • {status} • the existing relay was not changed"),
                    Red);
                AndroidRuntimeLog.Append("RENDER", $"Relay deploy failed service={created.Id} status={status}; existing relay preserved; secrets hidden");
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
            T("Render ยัง Deploy ไม่เสร็จ • Relay เดิมยังไม่ถูกเปลี่ยน", "Render is still deploying • the existing relay remains unchanged"),
            Amber);
        AndroidRuntimeLog.Append("RENDER", $"Relay deploy monitoring timed out service={created.Id}; existing relay preserved; secrets hidden");
    }

    private static bool IsRenderDeploySuccessful(string status) =>
        status is "live" or "succeeded" or "successful" or "deployed";

    private static bool IsRenderDeployFailed(string status) =>
        status.Contains("failed", StringComparison.OrdinalIgnoreCase)
        || status.Contains("canceled", StringComparison.OrdinalIgnoreCase)
        || status.Contains("cancelled", StringComparison.OrdinalIgnoreCase)
        || status.Contains("deactivated", StringComparison.OrdinalIgnoreCase);

    private void ApplyCreatedRenderRelayUrl(string serviceUrl, bool targetIsBackup)
    {
        if (!Uri.TryCreate(serviceUrl, UriKind.Absolute, out var uri)
            || !uri.Scheme.Equals("https", StringComparison.OrdinalIgnoreCase)
            || string.IsNullOrWhiteSpace(uri.Host))
            throw new RenderApiException("Render returned an invalid public service URL.");

        var cleanUrl = uri.GetLeftPart(UriPartial.Authority).TrimEnd('/');
        _renderCreatedServiceUrl = cleanUrl;
        var websocket = MakeWebSocketUrl(cleanUrl);
        if (!IsBridgeUrlValid(websocket))
            throw new RenderApiException("Unable to generate the Render Relay WebSocket URL.");

        if (targetIsBackup)
        {
            var backups = ServerPreferences.GetBridgeBackupUrls(this).ToList();
            if (backups.Count == 0)
                backups.Add(websocket);
            else
                backups[0] = websocket;
            ServerPreferences.SaveBridgeBackups(this, backups);
        }
        else
        {
            if (_renderUrl != null)
                _renderUrl.Text = cleanUrl;
            UpdateWebSocketFromRenderUrl();
            ServerPreferences.SaveBridge(this, true, websocket, CurrentServerId(), CurrentSecret());
        }

        RefreshBridgePreview();
    }

'''
    text = replace_required(text, methods_anchor, methods + methods_anchor, "Render provisioning methods")

    path.write_text(text, encoding="utf-8")
    final = path.read_text(encoding="utf-8")
    required = [
        'private const string RenderServiceName = "VoiceCraft by SamSoSleepy";',
        'private const string RenderRegion = "Singapore";',
        'private const string RenderPlan = "Free";',
        "RenderApiClient.FindServiceByNameAsync(",
        "BackupRelayPremiumGate.CanUseBackupRelayAsync(this)",
        "ChooseRenderTarget(false)",
        "ChooseRenderTarget(true)",
        "ApplyCreatedRenderRelayUrl(url, targetIsBackup)",
        "ServerPreferences.SaveBridgeBackups(this, backups)",
        "ServerPreferences.SaveBridge(this, true, websocket",
    ]
    missing = [value for value in required if value not in final]
    if missing:
        raise RuntimeError(f"Render setup UI validation failed: {missing}")

    forbidden = [
        "_renderWorkspace = new Spinner",
        "_renderRegion = new Spinner",
        "_renderPlan = new Spinner",
        "_renderServiceName = Input",
    ]
    present = [value for value in forbidden if value in final]
    if present:
        raise RuntimeError(f"Render fixed defaults validation failed: interactive selectors still present: {present}")

    print(f"Applied Render Relay provisioning UI to {path}")
    print("- workspace is selected automatically and service name is fixed to VoiceCraft by SamSoSleepy")
    print("- duplicate VoiceCraft Render services are blocked and require a different Render account/API key")
    print("- Primary/Backup target selection uses real VoiceCraft backup-relay entitlement")
    print("- Free Account locks Backup Relay; Premium/Admin can select it")
    print("- existing relay replacement requires confirmation and commits only after LIVE")
    print("- region fixed to Singapore and plan fixed to Free")
    print("- API key instructions are shown inline and the key remains session-only")


if __name__ == "__main__":
    main()
