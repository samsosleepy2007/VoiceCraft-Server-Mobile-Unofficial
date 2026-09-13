using Android.Content;
using Android.Views;
using Android.Widget;

namespace VoiceCraft.Server.Android;

/// <summary>
/// Managed Button wrapper used by the Android UI.
///
/// Important: .NET for Android generates the managed View.Touch event from a
/// Java listener that returns bool. The generated EventArgs.Handled value
/// defaults to true, so simply subscribing to Touch for animation can consume
/// the gesture and prevent the normal native Click/PerformClick pipeline.
///
/// ModernMainActivity uses Touch only for press animation. This first handler
/// explicitly keeps those touch events non-consuming so Android.Widget.Button
/// can still run its normal OnTouchEvent -> PerformClick path.
/// </summary>
internal sealed class Button : global::Android.Widget.Button
{
    internal Button(Context context) : base(context)
    {
        Touch += (_, e) =>
        {
            // Keep animation-only Touch handlers from swallowing the gesture.
            // Later handlers in ModernMainActivity do not change Handled, so
            // this remains false when the generated OnTouchListener returns.
            e.Handled = false;
        };
    }

    public new int MinHeight
    {
        set => SetMinHeight(value);
    }

    public new int MinWidth
    {
        set => SetMinWidth(value);
    }

    public override bool PerformClick()
    {
        var label = string.IsNullOrWhiteSpace(Text) ? "(unnamed)" : Text;

        try
        {
            return base.PerformClick();
        }
        catch (Exception ex)
        {
            // Keep failures diagnosable without recording routine button presses.
            AndroidRuntimeLog.Append(
                "UI",
                $"ACTION ERROR button={label}: {ex.GetType().Name}: {ex.Message}");

            try
            {
                Toast.MakeText(
                    Context,
                    $"Action failed: {ex.Message}",
                    ToastLength.Long)?.Show();
            }
            catch
            {
                // Never let diagnostic UI hide the original action failure.
            }

            return false;
        }
    }
}
