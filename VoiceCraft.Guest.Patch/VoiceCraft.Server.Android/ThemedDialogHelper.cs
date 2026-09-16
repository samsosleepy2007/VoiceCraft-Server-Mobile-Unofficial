using Android.App;
using Android.Graphics;
using Android.Graphics.Drawables;
using Android.Widget;

namespace VoiceCraft.Server.Android;

internal static class ThemedDialogHelper
{
    internal static AlertDialog.Builder Builder(Activity activity)
    {
        var dark = ServerPreferences.GetDarkTheme(activity);
        var style = ResolvePlatformDialogStyle(activity, dark);
        return style != 0
            ? new AlertDialog.Builder(activity, style)
            : new AlertDialog.Builder(activity);
    }

    private static int ResolvePlatformDialogStyle(Activity activity, bool dark)
    {
        var resources = activity.Resources;
        if (resources == null)
            return 0;

        var candidates = dark
            ? new[]
            {
                "Theme.Material.Dialog.Alert",
                "Theme.DeviceDefault.Dialog.Alert",
                "Theme.Material.Dialog",
                "Theme.DeviceDefault.Dialog"
            }
            : new[]
            {
                "Theme.Material.Light.Dialog.Alert",
                "Theme.DeviceDefault.Light.Dialog.Alert",
                "Theme.Material.Light.Dialog",
                "Theme.DeviceDefault.Light.Dialog"
            };

        foreach (var name in candidates)
        {
            var id = resources.GetIdentifier(name, "style", "android");
            if (id != 0)
                return id;
        }

        return 0;
    }

    internal static void StyleShown(AlertDialog dialog, Activity activity)
    {
        var dark = ServerPreferences.GetDarkTheme(activity);
        var surface = dark ? Color.Rgb(22, 30, 48) : Color.White;
        var ink = dark ? Color.Rgb(246, 248, 255) : Color.Rgb(35, 39, 54);
        var border = dark ? Color.Rgb(51, 63, 87) : Color.Rgb(228, 232, 244);
        var accent = dark ? Color.Rgb(92, 229, 160) : Color.Rgb(18, 153, 104);
        var density = activity.Resources?.DisplayMetrics?.Density ?? 1f;

        var background = new GradientDrawable();
        background.SetColor(surface);
        background.SetCornerRadius(22f * density);
        background.SetStroke(System.Math.Max(1, (int)(density + 0.5f)), border);
        dialog.Window?.SetBackgroundDrawable(background);

        if (dialog.FindViewById<TextView>(Android.Resource.Id.Message) is TextView message)
            message.SetTextColor(ink);

        var titleId = activity.Resources?.GetIdentifier("alertTitle", "id", "android") ?? 0;
        if (titleId != 0 && dialog.FindViewById<TextView>(titleId) is TextView title)
            title.SetTextColor(ink);

        dialog.GetButton(-1)?.SetTextColor(accent);
        dialog.GetButton(-2)?.SetTextColor(accent);
        dialog.GetButton(-3)?.SetTextColor(accent);
    }
}
