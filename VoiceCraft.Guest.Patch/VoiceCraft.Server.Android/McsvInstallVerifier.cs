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

    internal static async Task VerifyConfigAndActiveWorldAsync(
        McsvApiClient api,
        string expectedServerId,
        Action<string>? progress,
        CancellationToken cancellationToken)
    {
        progress?.Invoke("Verifying VoiceCraft config and active world…");

        var config = await McsvEndweaveSupport.ReadTextAsync(
            api,
            "/plugins/voicecraft/config.toml",
            cancellationToken);
        if (!config.Contains("[bridge]", StringComparison.Ordinal) ||
            !config.Contains("enabled = true", StringComparison.Ordinal) ||
            !config.Contains("[voice_range]", StringComparison.Ordinal) ||
            !config.Contains(
                $"server_id = \"{Toml(expectedServerId.Trim())}\"",
                StringComparison.Ordinal))
            throw new McsvApiException(
                "VoiceCraft config.toml verification failed after writing Relay/Voice Range configuration.");

        var properties = await McsvEndweaveSupport.ReadTextAsync(
            api,
            "/server.properties",
            cancellationToken);
        var levelName = ParseLevelName(properties);
        if (string.IsNullOrWhiteSpace(levelName))
            levelName = "Bedrock level";
        if (levelName.Contains('/') || levelName.Contains('\\') || levelName.Contains("..", StringComparison.Ordinal))
            throw new McsvApiException("Unsafe level-name detected while verifying Item Mic world activation.");

        var worldRoot = "/worlds/" + levelName;
        var behaviorPacks = await McsvEndweaveSupport.ReadTextAsync(
            api,
            worldRoot + "/world_behavior_packs.json",
            cancellationToken);
        var resourcePacks = await McsvEndweaveSupport.ReadTextAsync(
            api,
            worldRoot + "/world_resource_packs.json",
            cancellationToken);

        VerifyPackList(
            behaviorPacks,
            ItemMicBehaviorPackUuid,
            worldRoot + "/world_behavior_packs.json");
        VerifyPackList(
            resourcePacks,
            ItemMicResourcePackUuid,
            worldRoot + "/world_resource_packs.json");
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

    private static void VerifyPackList(string json, string expectedUuid, string path)
    {
        try
        {
            using var document = JsonDocument.Parse(json);
            if (document.RootElement.ValueKind != JsonValueKind.Array)
                throw new McsvApiException($"{path} is not a JSON array.");

            foreach (var item in document.RootElement.EnumerateArray())
            {
                if (item.ValueKind != JsonValueKind.Object ||
                    !item.TryGetProperty("pack_id", out var packId) ||
                    packId.ValueKind != JsonValueKind.String ||
                    !string.Equals(packId.GetString(), expectedUuid, StringComparison.OrdinalIgnoreCase))
                    continue;

                if (!item.TryGetProperty("version", out var version) ||
                    version.ValueKind != JsonValueKind.Array ||
                    version.GetArrayLength() != 3)
                    throw new McsvApiException($"VoiceCraft Item Mic pack has an invalid version entry in {path}.");

                var values = version.EnumerateArray().Select(value => value.GetInt32()).ToArray();
                if (values.SequenceEqual(new[] { 2, 4, 0 }))
                    return;

                throw new McsvApiException(
                    $"VoiceCraft Item Mic pack version in {path} is not 2.4.0.");
            }

            throw new McsvApiException(
                $"VoiceCraft Item Mic pack {expectedUuid} is not enabled in {path}.");
        }
        catch (JsonException)
        {
            throw new McsvApiException($"{path} is invalid JSON after Item Mic activation.");
        }
    }

    private static string ParseLevelName(string serverProperties)
    {
        using var reader = new StringReader(serverProperties ?? string.Empty);
        while (reader.ReadLine() is { } line)
        {
            var trimmed = line.Trim();
            if (trimmed.StartsWith("#", StringComparison.Ordinal) ||
                !trimmed.StartsWith("level-name=", StringComparison.OrdinalIgnoreCase))
                continue;
            return trimmed["level-name=".Length..].Trim();
        }
        return string.Empty;
    }

    private static string Toml(string value) =>
        (value ?? string.Empty)
            .Replace("\\", "\\\\", StringComparison.Ordinal)
            .Replace("\"", "\\\"", StringComparison.Ordinal)
            .Replace("\r", string.Empty, StringComparison.Ordinal)
            .Replace("\n", string.Empty, StringComparison.Ordinal);

    private static void RequireFile(
        IEnumerable<McsvEndweaveFileEntry> entries,
        string name,
        string error)
    {
        if (!entries.Any(entry => entry.IsFile && entry.Name.Equals(name, StringComparison.Ordinal)))
            throw new McsvApiException(error);
    }
}
