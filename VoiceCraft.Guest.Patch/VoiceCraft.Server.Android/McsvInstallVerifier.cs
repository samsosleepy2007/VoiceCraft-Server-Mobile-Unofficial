using System.Text.Json;

namespace VoiceCraft.Server.Android;

internal static class McsvInstallVerifier
{
    internal const string ItemMicBehaviorPackPath = "/behavior_packs/VoiceCraft_ItemMic_BP";
    internal const string ItemMicResourcePackPath = "/resource_packs/VoiceCraft_ItemMic_RP";
    internal const string ItemMicBehaviorPackUuid = "b6411120-cc4e-44a9-b28d-f43b10cafd86";
    internal const string ItemMicResourcePackUuid = "cb345edb-6e6c-49ac-9950-e2ae07bda214";

    internal static async Task VerifyItemMicFilesAsync(
        McsvApiClient api,
        Action<string>? progress,
        CancellationToken cancellationToken)
    {
        progress?.Invoke("Verifying Item Mic add-on files…");

        var behaviorPack = await McsvEndweaveSupport.ListAsync(
            api,
            ItemMicBehaviorPackPath,
            cancellationToken);
        RequireFile(
            behaviorPack,
            "manifest.json",
            "Item Mic Behavior Pack is missing manifest.json after installation.");

        var resourcePack = await McsvEndweaveSupport.ListAsync(
            api,
            ItemMicResourcePackPath,
            cancellationToken);
        RequireFile(
            resourcePack,
            "manifest.json",
            "Item Mic Resource Pack is missing manifest.json after installation.");

        await ValidatePackManifestAsync(
            api,
            ItemMicBehaviorPackPath + "/manifest.json",
            ItemMicBehaviorPackUuid,
            "Behavior Pack",
            cancellationToken);
        await ValidatePackManifestAsync(
            api,
            ItemMicResourcePackPath + "/manifest.json",
            ItemMicResourcePackUuid,
            "Resource Pack",
            cancellationToken);
    }

    private static async Task ValidatePackManifestAsync(
        McsvApiClient api,
        string path,
        string expectedUuid,
        string label,
        CancellationToken cancellationToken)
    {
        var text = await McsvEndweaveSupport.ReadTextAsync(api, path, cancellationToken);
        try
        {
            using var document = JsonDocument.Parse(text);
            var root = document.RootElement;
            if (root.ValueKind != JsonValueKind.Object ||
                !root.TryGetProperty("header", out var header) ||
                header.ValueKind != JsonValueKind.Object ||
                !header.TryGetProperty("uuid", out var uuid) ||
                uuid.ValueKind != JsonValueKind.String ||
                !string.Equals(uuid.GetString(), expectedUuid, StringComparison.OrdinalIgnoreCase))
                throw new McsvApiException(
                    $"Item Mic {label} manifest UUID does not match the expected VoiceCraft 2.4.0 pack.");
        }
        catch (JsonException)
        {
            throw new McsvApiException($"Item Mic {label} manifest is invalid JSON: {path}");
        }
    }

    private static void RequireFile(
        IEnumerable<McsvEndweaveFileEntry> entries,
        string name,
        string error)
    {
        if (!entries.Any(entry => entry.IsFile && entry.Name.Equals(name, StringComparison.Ordinal)))
            throw new McsvApiException(error);
    }
}
