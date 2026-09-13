using System.Net.Http.Headers;
using System.Text.Json;
using Android.App;
using Android.Content;
using Android.Database;
using Android.OS;
using Android.Widget;
using AndroidUri = Android.Net.Uri;

namespace VoiceCraft.Server.Android;

[ContentProvider(new[] { "chat.voicecraft.server.backuprelaypremiumgate" }, Exported = false, InitOrder = 1080)]
public sealed class BackupRelayPremiumGateProvider : ContentProvider
{
    private BackupRelayPremiumGateLifecycle? _callbacks;

    public override bool OnCreate()
    {
        try
        {
            if (Context?.ApplicationContext is Application app)
            {
                _callbacks = new BackupRelayPremiumGateLifecycle();
                app.RegisterActivityLifecycleCallbacks(_callbacks);
            }
        }
        catch (Exception ex)
        {
            AndroidRuntimeLog.Append("UI", $"Backup relay Premium gate unavailable: {ex.GetType().Name}: {ex.Message}");
        }

        return true;
    }

    public override ICursor? Query(AndroidUri uri, string[]? projection, string? selection, string[]? selectionArgs, string? sortOrder) => null;
    public override string? GetType(AndroidUri uri) => null;
    public override AndroidUri? Insert(AndroidUri uri, ContentValues? values) => null;
    public override int Delete(AndroidUri uri, string? selection, string[]? selectionArgs) => 0;
    public override int Update(AndroidUri uri, ContentValues? values, string? selection, string[]? selectionArgs) => 0;
}

internal sealed class BackupRelayPremiumGateLifecycle : Java.Lang.Object, Application.IActivityLifecycleCallbacks
{
    private readonly HashSet<Activity> _checked = new();

    public void OnActivityCreated(Activity activity, Bundle? savedInstanceState) { }
    public void OnActivityStarted(Activity activity) { }

    public async void OnActivityResumed(Activity activity)
    {
        if (activity is not BackupRelayActivity || _checked.Contains(activity))
            return;

        _checked.Add(activity);
        await BackupRelayPremiumGate.VerifyOrCloseAsync(activity);
    }

    public void OnActivityPaused(Activity activity) { }
    public void OnActivityStopped(Activity activity) { }
    public void OnActivitySaveInstanceState(Activity activity, Bundle outState) { }
    public void OnActivityDestroyed(Activity activity) => _checked.Remove(activity);
}

internal static class BackupRelayPremiumGate
{
    private static readonly HttpClient Http = new()
    {
        Timeout = TimeSpan.FromSeconds(15)
    };

    internal static async Task<bool> CanUseBackupRelayAsync(Context context)
    {
        if (!RegisteredSessionStore.TryLoad(context, out var session) || session == null)
            return false;

        try
        {
            using var request = new HttpRequestMessage(
                HttpMethod.Get,
                AccountApiConfig.AccountApiBase + "/v1/entitlements");
            request.Headers.Authorization = new AuthenticationHeaderValue("Bearer", session.Token);

            using var response = await Http.SendAsync(request);
            var text = await response.Content.ReadAsStringAsync();

            if (response.StatusCode == System.Net.HttpStatusCode.Unauthorized)
            {
                RegisteredSessionStore.Delete(context);
                AndroidRuntimeLog.Append("ACCOUNT", "Backup relay entitlement session expired");
                return false;
            }

            if (!response.IsSuccessStatusCode)
            {
                AndroidRuntimeLog.Append("ACCOUNT", $"Backup relay entitlement returned HTTP {(int)response.StatusCode}");
                return false;
            }

            using var doc = JsonDocument.Parse(text);
            var allowed = doc.RootElement.TryGetProperty("capabilities", out var capabilities)
                && capabilities.TryGetProperty("backupRelays", out var backupRelays)
                && backupRelays.ValueKind == JsonValueKind.True;

            AndroidRuntimeLog.Append("ACCOUNT", allowed
                ? "Backup relay entitlement available"
                : "Backup relay entitlement unavailable");
            return allowed;
        }
        catch (Exception ex)
        {
            AndroidRuntimeLog.Append("ACCOUNT", $"Backup relay entitlement check failed: {ex.GetType().Name}");
            return false;
        }
    }

    public static async Task<bool> VerifyOrCloseAsync(Activity activity)
    {
        var thai = ServerPreferences.GetLanguage(activity) == "th";

        if (!RegisteredSessionStore.TryLoad(activity, out var session) || session == null)
        {
            ShowPremiumRequired(activity, thai);
            return false;
        }

        try
        {
            using var request = new HttpRequestMessage(
                HttpMethod.Get,
                AccountApiConfig.AccountApiBase + "/v1/entitlements");
            request.Headers.Authorization = new AuthenticationHeaderValue("Bearer", session.Token);

            using var response = await Http.SendAsync(request);
            var text = await response.Content.ReadAsStringAsync();

            if (response.StatusCode == System.Net.HttpStatusCode.Unauthorized)
            {
                RegisteredSessionStore.Delete(activity);
                ShowVerificationFailed(
                    activity,
                    thai,
                    thai ? "เซสชันหมดอายุ กรุณาเข้าสู่ระบบอีกครั้ง" : "Your session expired. Please sign in again.");
                return false;
            }

            if (!response.IsSuccessStatusCode)
            {
                ShowVerificationFailed(
                    activity,
                    thai,
                    thai ? "ไม่สามารถตรวจสอบสิทธิ์บัญชีได้ในขณะนี้" : "Account access could not be verified right now.");
                return false;
            }

            using var doc = JsonDocument.Parse(text);
            var allowed = doc.RootElement.TryGetProperty("capabilities", out var capabilities)
                && capabilities.TryGetProperty("backupRelays", out var backupRelays)
                && backupRelays.ValueKind == JsonValueKind.True;

            if (!allowed)
            {
                ShowPremiumRequired(activity, thai);
                return false;
            }

            AndroidRuntimeLog.Append("ACCOUNT", "Backup relay entitlement verified");
            return true;
        }
        catch (Exception ex)
        {
            AndroidRuntimeLog.Append("ACCOUNT", $"Backup relay entitlement check failed: {ex.GetType().Name}: {ex.Message}");
            ShowVerificationFailed(
                activity,
                thai,
                thai ? "เชื่อมต่อระบบบัญชีไม่ได้ จึงยังไม่สามารถเปิด Backup Relay ได้" : "Could not reach the account service, so Backup Relays cannot be opened yet.");
            return false;
        }
    }

    private static void ShowPremiumRequired(Activity activity, bool thai)
    {
        try
        {
            new AlertDialog.Builder(activity)
                .SetTitle(thai ? "Backup Relay สำหรับ Premium" : "Premium Backup Relays")
                .SetMessage(thai
                    ? "Free Account ไม่สามารถเพิ่ม Backup Render Relay ได้ ฟีเจอร์นี้ใช้ได้เฉพาะบัญชี Premium หรือ Admin เท่านั้น"
                    : "Free Accounts cannot add Backup Render Relays. This feature is available only to Premium or Admin accounts.")
                .SetPositiveButton("OK", (_, _) => activity.Finish())
                .SetOnCancelListener(new FinishOnCancel(activity))
                .Show();
        }
        catch
        {
            Toast.MakeText(
                activity,
                thai ? "Backup Relay ใช้ได้เฉพาะ Premium หรือ Admin" : "Backup Relays require Premium or Admin",
                ToastLength.Long)?.Show();
            activity.Finish();
        }
    }

    private static void ShowVerificationFailed(Activity activity, bool thai, string message)
    {
        try
        {
            new AlertDialog.Builder(activity)
                .SetTitle(thai ? "ตรวจสอบบัญชีไม่สำเร็จ" : "Account verification failed")
                .SetMessage(message)
                .SetPositiveButton("OK", (_, _) => activity.Finish())
                .SetOnCancelListener(new FinishOnCancel(activity))
                .Show();
        }
        catch
        {
            Toast.MakeText(activity, message, ToastLength.Long)?.Show();
            activity.Finish();
        }
    }

    private sealed class FinishOnCancel : Java.Lang.Object, IDialogInterfaceOnCancelListener
    {
        private readonly Activity _activity;
        public FinishOnCancel(Activity activity) => _activity = activity;
        public void OnCancel(IDialogInterface? dialog) => _activity.Finish();
    }
}
