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
        var style = dark
            ? Android.Resource.Style.ThemeMaterialDialogAlert
            : Android.Resource.Style.ThemeMaterialLightDialogAlert;
        return new AlertDialog.Builder(activity, style);
    }

    internal static void StyleShown(AlertDialog dialog, Activity activity)
    {
        var dark = ServerPreferences.GetDarkTheme(activity);
        var surface = dark ? Color.Rgb(22, 30, 48) : Color.White;
        var ink = dark ? Color.Rgb(246, 248, 255) : Color.Rgb(35, 39, 54);
        var border = dark ? Color.Rgb(51, 63, 87) : Color.Rgb(228, 232, 244);
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
    }
}
