using Android.Content;

namespace VoiceCraft.Server.Android;

internal static class McsvTokenStore
{
    private sealed class StoredToken
    {
        public string ApiKey { get; set; } = string.Empty;
    }

    private static readonly KeystoreJsonStore Store = new(
        "voicecraft_mcsv_api_key_v1",
        "mcsv_api_key_v1.json");

    internal static void Save(Context context, string apiKey)
    {
        var value = (apiKey ?? string.Empty).Trim();
        if (!value.StartsWith("mcsv_", StringComparison.Ordinal))
            throw new ArgumentException("Invalid MCSV API key format.", nameof(apiKey));

        Store.Save(context, new StoredToken { ApiKey = value });
    }

    internal static bool TryLoad(Context context, out string apiKey)
    {
        apiKey = string.Empty;
        if (!Store.TryLoad<StoredToken>(context, out var stored) || stored == null)
            return false;

        var value = (stored.ApiKey ?? string.Empty).Trim();
        if (!value.StartsWith("mcsv_", StringComparison.Ordinal))
            return false;

        apiKey = value;
        return true;
    }

    internal static void Delete(Context context) => Store.Delete(context);
}
