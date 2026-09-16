using System.Text.Json;

namespace VoiceCraft.Server.Android;

internal sealed record McsvEndweavePreflight(
    string ServerName,
    string Game,
    string ServerType,
    string RuntimeRoot);

internal static class McsvEndweaveSupport
{
    internal const string EndstoneRuntimeRoot = "/.endstone-runtime";

    internal static async Task<McsvEndweavePreflight> ValidatePreflightAsync(
        McsvApiClient api,
        JsonElement serverInfo,
        CancellationToken cancellationToken)
    {
        var serverName = StringProperty(serverInfo, "name", "MCSV Server");
        var game = StringProperty(serverInfo, "game", string.Empty);
        var serverType = StringProperty(serverInfo, "server_type", string.Empty);

        if (!ContainsBedrockOrEndstone(game) && !ContainsBedrockOrEndstone(serverType))
            throw new McsvApiException(
                $"This MCSV API key belongs to '{serverType}/{game}', not a Bedrock/Endstone server.");

        var root = await ListAsync(api, "/", cancellationToken);
        RequireDirectory(root, "plugins", "Endstone was not detected: /plugins is missing.");
        RequireDirectory(root, "worlds", "Bedrock worlds directory was not found.");
        RequireFile(root, "server.properties", "/server.properties was not found.");
        RequireDirectory(
            root,
            ".endstone-runtime",
            "Endstone runtime was not detected: /.endstone-runtime is missing. Start Endstone at least once before automatic installation.");

        var runtimeRoot = await ListAsync(api, EndstoneRuntimeRoot, cancellationToken);
        if (!runtimeRoot.Any(entry => !entry.IsFile))
            throw new McsvApiException(
                "Endstone runtime directory is empty. Start the Endstone server once and try again.");

        return new McsvEndweavePreflight(serverName, game, serverType, EndstoneRuntimeRoot);
    }

    internal static async Task<List<McsvEndweaveFileEntry>> ListAsync(
        McsvApiClient api,
        string directory,
        CancellationToken cancellationToken)
    {
        var root = McsvApiClient.UnwrapResult(
            await api.CallToolAsync(
                "files_list",
                new { directory },
                cancellationToken));

        var result = new List<McsvEndweaveFileEntry>();
        if (root.ValueKind != JsonValueKind.Object ||
            !root.TryGetProperty("files", out var files) ||
            files.ValueKind != JsonValueKind.Array)
            return result;

        foreach (var item in files.EnumerateArray())
        {
            if (item.ValueKind != JsonValueKind.Object ||
                !item.TryGetProperty("name", out var name) ||
                name.ValueKind != JsonValueKind.String)
                continue;

            var isFile = item.TryGetProperty("is_file", out var fileValue) &&
                         fileValue.ValueKind == JsonValueKind.True;
            result.Add(new McsvEndweaveFileEntry(name.GetString() ?? string.Empty, isFile));
        }

        return result;
    }

    internal static async Task<string> ReadTextAsync(
        McsvApiClient api,
        string path,
        CancellationToken cancellationToken)
    {
        var root = McsvApiClient.UnwrapResult(
            await api.CallToolAsync(
                "files_read",
                new { path },
                cancellationToken));

        if (root.ValueKind == JsonValueKind.Object &&
            root.TryGetProperty("content", out var content) &&
            content.ValueKind == JsonValueKind.String)
            return content.GetString() ?? string.Empty;

        throw new McsvApiException("MCSV did not return text for " + path);
    }

    private static void RequireDirectory(
        IEnumerable<McsvEndweaveFileEntry> entries,
        string name,
        string error)
    {
        if (!entries.Any(entry => !entry.IsFile && entry.Name.Equals(name, StringComparison.Ordinal)))
            throw new McsvApiException(error);
    }

    private static void RequireFile(
        IEnumerable<McsvEndweaveFileEntry> entries,
        string name,
        string error)
    {
        if (!entries.Any(entry => entry.IsFile && entry.Name.Equals(name, StringComparison.Ordinal)))
            throw new McsvApiException(error);
    }

    private static bool ContainsBedrockOrEndstone(string value) =>
        value.Contains("bedrock", StringComparison.OrdinalIgnoreCase) ||
        value.Contains("endstone", StringComparison.OrdinalIgnoreCase);

    private static string StringProperty(JsonElement element, string name, string fallback)
    {
        if (element.ValueKind == JsonValueKind.Object &&
            element.TryGetProperty(name, out var value) &&
            value.ValueKind == JsonValueKind.String)
            return value.GetString() ?? fallback;
        return fallback;
    }
}

internal sealed record McsvEndweaveFileEntry(string Name, bool IsFile);
