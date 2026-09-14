using System.Text;
using System.Text.Json;
using System.Text.Json.Nodes;

namespace VoiceCraft.Server.Android;

internal sealed class McsvInstallResult
{
    internal string ServerName { get; init; } = string.Empty;
    internal bool RestartRequested { get; init; }
    internal bool ServerRunning { get; init; }
    internal string Warning { get; init; } = string.Empty;
}

internal static class McsvVoiceCraftInstaller
{
    private const string PluginWheelName = "endstone_voicecraft-0.2.8-py3-none-any.whl";
    private const string PluginWheelUrl =
        "https://github.com/samsosleepy2007/VoiceCraft-Server-Mobile-Unofficial/releases/download/" +
        "v1.7.1-android-phase2-ui5-voice-range-strongfade50-endstone0.2.8-relay0.2.1-itemmic2.3.0/" +
        PluginWheelName;

    private const string ItemMicUrl =
        "https://github.com/samsosleepy2007/VoiceCraft-Server-Mobile-Unofficial/releases/download/" +
        "v1.7.1-itemmic2.4.0-hidden-single/VoiceCraft_ItemMic_v2.4.0.mcaddon";

    private const string ItemMicBpPack = "VoiceCraft_ItemMic_BP_v2.4.0.mcpack";
    private const string ItemMicRpPack = "VoiceCraft_ItemMic_RP_v2.4.0.mcpack";
    private const string ItemMicBpUuid = "b6411120-cc4e-44a9-b28d-f43b10cafd86";
    private const string ItemMicRpUuid = "cb345edb-6e6c-49ac-9950-e2ae07bda214";
    private const string StageName = "voicecraft_auto_install";

    private static readonly string[] RequiredTools =
    {
        "server_info",
        "files_list",
        "files_read",
        "files_write",
        "files_mkdir",
        "files_delete",
        "files_rename",
        "files_decompress",
        "files_fetch_url",
        "power_action"
    };

    internal static async Task<McsvInstallResult> InstallAsync(
        string apiKey,
        string relayWebSocket,
        IReadOnlyList<string> backupRelays,
        string serverId,
        string bridgeSecret,
        Action<string>? progress = null,
        CancellationToken cancellationToken = default)
    {
        progress ??= _ => { };
        using var api = new McsvApiClient(apiKey);

        progress("Checking MCSV API…");
        await api.ValidateKeyAsync(cancellationToken);
        var allowedTools = await api.GetAllowedToolsAsync(cancellationToken);
        var missing = RequiredTools.Where(tool => !allowedTools.Contains(tool)).ToArray();
        if (missing.Length > 0)
            throw new McsvApiException(
                "MCSV API key is missing required permissions: " + string.Join(", ", missing));

        var serverInfo = McsvApiClient.UnwrapResult(
            await api.CallToolAsync("server_info", cancellationToken: cancellationToken));
        var serverName = StringProperty(serverInfo, "name", "MCSV Server");
        var game = StringProperty(serverInfo, "game", string.Empty);
        var serverType = StringProperty(serverInfo, "server_type", string.Empty);
        if (!ContainsBedrockOrEndstone(game) && !ContainsBedrockOrEndstone(serverType))
            throw new McsvApiException(
                $"This MCSV API key belongs to '{serverType}/{game}', not a Bedrock/Endstone server.");

        var root = await ListAsync(api, "/", cancellationToken);
        if (!root.Any(entry => !entry.IsFile && entry.Name.Equals("plugins", StringComparison.Ordinal)))
            throw new McsvApiException(
                "Endstone was not detected: the /plugins directory is missing. Use an Endstone-compatible Bedrock build first.");
        if (!root.Any(entry => !entry.IsFile && entry.Name.Equals("worlds", StringComparison.Ordinal)))
            throw new McsvApiException("Bedrock worlds directory was not found on this server.");
        if (!root.Any(entry => entry.IsFile && entry.Name.Equals("server.properties", StringComparison.Ordinal)))
            throw new McsvApiException("/server.properties was not found on this server.");

        var warning = string.Empty;
        if (allowedTools.Contains("backups_create"))
        {
            progress("Creating safety backup…");
            try
            {
                await api.CallToolAsync(
                    "backups_create",
                    new { name = "voicecraft-auto-install" },
                    cancellationToken);
            }
            catch (Exception ex)
            {
                warning = "Backup could not be created: " + SafeMessage(ex);
            }
        }

        progress("Installing Endstone plugin…");
        await InstallPluginAsync(api, cancellationToken);

        progress("Writing VoiceCraft config…");
        await WritePluginConfigAsync(
            api,
            BuildPluginConfig(relayWebSocket, backupRelays, serverId, bridgeSecret),
            cancellationToken);

        progress("Installing Item Mic add-on…");
        await InstallItemMicAsync(api, cancellationToken);

        progress("Enabling add-on in active world…");
        await EnableItemMicForActiveWorldAsync(api, cancellationToken);

        // Restart only after every required installation step has succeeded.
        progress("Restarting MCSV server…");
        await api.CallToolAsync(
            "power_action",
            new { action = "restart" },
            cancellationToken);

        var running = false;
        if (allowedTools.Contains("server_overview"))
        {
            progress("Waiting for MCSV server…");
            running = await WaitUntilRunningAsync(api, cancellationToken);
        }

        progress(running ? "Installation complete — server online" : "Installation complete — restart requested");
        return new McsvInstallResult
        {
            ServerName = serverName,
            RestartRequested = true,
            ServerRunning = running,
            Warning = warning
        };
    }

    private static async Task InstallPluginAsync(McsvApiClient api, CancellationToken cancellationToken)
    {
        var plugins = await ListAsync(api, "/plugins", cancellationToken);
        var oldWheels = plugins
            .Where(entry => entry.IsFile &&
                entry.Name.StartsWith("endstone_voicecraft-", StringComparison.OrdinalIgnoreCase) &&
                entry.Name.EndsWith(".whl", StringComparison.OrdinalIgnoreCase))
            .Select(entry => entry.Name)
            .ToArray();

        if (oldWheels.Length > 0)
        {
            await api.CallToolAsync(
                "files_delete",
                new { root = "/plugins", files = oldWheels },
                cancellationToken);
        }

        await api.CallToolAsync(
            "files_fetch_url",
            new
            {
                url = PluginWheelUrl,
                directory = "/plugins/",
                filename = PluginWheelName
            },
            cancellationToken);

        await EnsureDirectoryAsync(api, "/plugins", "voicecraft", cancellationToken);
    }

    private static async Task WritePluginConfigAsync(
        McsvApiClient api,
        string config,
        CancellationToken cancellationToken)
    {
        var pluginData = await ListAsync(api, "/plugins/voicecraft", cancellationToken);
        var exists = pluginData.Any(entry => entry.IsFile && entry.Name.Equals("config.toml", StringComparison.Ordinal));
        if (exists)
            await ReadTextAsync(api, "/plugins/voicecraft/config.toml", cancellationToken);

        await api.CallToolAsync(
            "files_write",
            new
            {
                path = "/plugins/voicecraft/config.toml",
                content = config,
                force_new = !exists
            },
            cancellationToken);
    }

    private static async Task InstallItemMicAsync(McsvApiClient api, CancellationToken cancellationToken)
    {
        var root = await ListAsync(api, "/", cancellationToken);
        if (root.Any(entry => !entry.IsFile && entry.Name.Equals(StageName, StringComparison.Ordinal)))
        {
            await api.CallToolAsync(
                "files_delete",
                new { root = "/", files = new[] { StageName } },
                cancellationToken);
        }

        await api.CallToolAsync(
            "files_mkdir",
            new { root = "/", name = StageName },
            cancellationToken);

        await api.CallToolAsync(
            "files_fetch_url",
            new
            {
                url = ItemMicUrl,
                directory = "/" + StageName,
                filename = "itemmic.zip"
            },
            cancellationToken);

        await api.CallToolAsync(
            "files_decompress",
            new { root = "/" + StageName, file = "itemmic.zip" },
            cancellationToken);

        var staged = await ListAsync(api, "/" + StageName, cancellationToken);
        RequireFile(staged, ItemMicBpPack);
        RequireFile(staged, ItemMicRpPack);

        await EnsureDirectoryAsync(api, "/" + StageName, "bp", cancellationToken);
        await EnsureDirectoryAsync(api, "/" + StageName, "rp", cancellationToken);

        await api.CallToolAsync(
            "files_rename",
            new
            {
                root = "/" + StageName,
                renames = new object[]
                {
                    new Dictionary<string, string> { ["from"] = ItemMicBpPack, ["to"] = "bp/pack.zip" },
                    new Dictionary<string, string> { ["from"] = ItemMicRpPack, ["to"] = "rp/pack.zip" }
                }
            },
            cancellationToken);

        await api.CallToolAsync(
            "files_decompress",
            new { root = "/" + StageName + "/bp", file = "pack.zip" },
            cancellationToken);
        await api.CallToolAsync(
            "files_decompress",
            new { root = "/" + StageName + "/rp", file = "pack.zip" },
            cancellationToken);

        await api.CallToolAsync(
            "files_delete",
            new { root = "/" + StageName, files = new[] { "itemmic.zip", "bp/pack.zip", "rp/pack.zip" } },
            cancellationToken);

        await EnsureDirectoryAsync(api, "/", "behavior_packs", cancellationToken);
        await EnsureDirectoryAsync(api, "/", "resource_packs", cancellationToken);

        await DeleteIfPresentAsync(api, "/behavior_packs", "VoiceCraft_ItemMic_BP", cancellationToken);
        await DeleteIfPresentAsync(api, "/resource_packs", "VoiceCraft_ItemMic_RP", cancellationToken);

        await api.CallToolAsync(
            "files_rename",
            new
            {
                root = "/",
                renames = new object[]
                {
                    new Dictionary<string, string>
                    {
                        ["from"] = StageName + "/bp",
                        ["to"] = "behavior_packs/VoiceCraft_ItemMic_BP"
                    },
                    new Dictionary<string, string>
                    {
                        ["from"] = StageName + "/rp",
                        ["to"] = "resource_packs/VoiceCraft_ItemMic_RP"
                    }
                }
            },
            cancellationToken);

        var afterMove = await ListAsync(api, "/", cancellationToken);
        if (afterMove.Any(entry => !entry.IsFile && entry.Name.Equals(StageName, StringComparison.Ordinal)))
        {
            await api.CallToolAsync(
                "files_delete",
                new { root = "/", files = new[] { StageName } },
                cancellationToken);
        }
    }

    private static async Task EnableItemMicForActiveWorldAsync(
        McsvApiClient api,
        CancellationToken cancellationToken)
    {
        var properties = await ReadTextAsync(api, "/server.properties", cancellationToken);
        var levelName = ParseLevelName(properties);
        if (string.IsNullOrWhiteSpace(levelName))
            levelName = "Bedrock level";
        if (levelName.Contains('/') || levelName.Contains('\\') || levelName.Contains("..", StringComparison.Ordinal))
            throw new McsvApiException("Unsafe level-name in server.properties; add-on activation stopped.");

        var worlds = await ListAsync(api, "/worlds", cancellationToken);
        if (!worlds.Any(entry => !entry.IsFile && entry.Name.Equals(levelName, StringComparison.Ordinal)))
            throw new McsvApiException($"Active world '/worlds/{levelName}' was not found.");

        var worldRoot = "/worlds/" + levelName;
        await UpsertPackListAsync(
            api,
            worldRoot,
            "world_behavior_packs.json",
            ItemMicBpUuid,
            cancellationToken);
        await UpsertPackListAsync(
            api,
            worldRoot,
            "world_resource_packs.json",
            ItemMicRpUuid,
            cancellationToken);
    }

    private static async Task UpsertPackListAsync(
        McsvApiClient api,
        string worldRoot,
        string fileName,
        string packId,
        CancellationToken cancellationToken)
    {
        var worldFiles = await ListAsync(api, worldRoot, cancellationToken);
        var exists = worldFiles.Any(entry => entry.IsFile && entry.Name.Equals(fileName, StringComparison.Ordinal));
        var path = worldRoot + "/" + fileName;
        var existing = exists ? await ReadTextAsync(api, path, cancellationToken) : "[]";

        JsonArray array;
        try
        {
            array = JsonNode.Parse(existing) as JsonArray ?? new JsonArray();
        }
        catch (JsonException)
        {
            throw new McsvApiException($"{path} is not valid JSON; it was not overwritten.");
        }

        for (var i = array.Count - 1; i >= 0; i--)
        {
            if (array[i] is JsonObject obj &&
                string.Equals(obj["pack_id"]?.GetValue<string>(), packId, StringComparison.OrdinalIgnoreCase))
                array.RemoveAt(i);
        }

        array.Add(new JsonObject
        {
            ["pack_id"] = packId,
            ["version"] = new JsonArray(
                JsonValue.Create(2),
                JsonValue.Create(4),
                JsonValue.Create(0))
        });

        await api.CallToolAsync(
            "files_write",
            new
            {
                path,
                content = array.ToJsonString(new JsonSerializerOptions { WriteIndented = true }) + "\n",
                force_new = !exists
            },
            cancellationToken);
    }

    private static async Task<bool> WaitUntilRunningAsync(
        McsvApiClient api,
        CancellationToken cancellationToken)
    {
        for (var i = 0; i < 30; i++)
        {
            await Task.Delay(TimeSpan.FromSeconds(3), cancellationToken);
            try
            {
                var root = McsvApiClient.UnwrapResult(
                    await api.CallToolAsync("server_overview", cancellationToken: cancellationToken));
                if (root.ValueKind == JsonValueKind.Object &&
                    root.TryGetProperty("runtime", out var runtime) &&
                    runtime.ValueKind == JsonValueKind.Object &&
                    runtime.TryGetProperty("current_state", out var state) &&
                    string.Equals(state.GetString(), "running", StringComparison.OrdinalIgnoreCase))
                    return true;
            }
            catch (McsvApiException ex) when (ex.StatusCode == 409 || ex.StatusCode == 400)
            {
                // The server may be between stopping and starting during a restart.
            }
        }
        return false;
    }

    private static async Task<List<McsvFileEntry>> ListAsync(
        McsvApiClient api,
        string directory,
        CancellationToken cancellationToken)
    {
        var root = McsvApiClient.UnwrapResult(
            await api.CallToolAsync(
                "files_list",
                new { directory },
                cancellationToken));
        var result = new List<McsvFileEntry>();
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
            var isFile = item.TryGetProperty("is_file", out var fileValue) && fileValue.ValueKind == JsonValueKind.True;
            result.Add(new McsvFileEntry(name.GetString() ?? string.Empty, isFile));
        }
        return result;
    }

    private static async Task<string> ReadTextAsync(
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

    private static async Task EnsureDirectoryAsync(
        McsvApiClient api,
        string root,
        string name,
        CancellationToken cancellationToken)
    {
        var entries = await ListAsync(api, root, cancellationToken);
        if (entries.Any(entry => !entry.IsFile && entry.Name.Equals(name, StringComparison.Ordinal)))
            return;
        await api.CallToolAsync(
            "files_mkdir",
            new { root, name },
            cancellationToken);
    }

    private static async Task DeleteIfPresentAsync(
        McsvApiClient api,
        string root,
        string name,
        CancellationToken cancellationToken)
    {
        var entries = await ListAsync(api, root, cancellationToken);
        if (!entries.Any(entry => entry.Name.Equals(name, StringComparison.Ordinal)))
            return;
        await api.CallToolAsync(
            "files_delete",
            new { root, files = new[] { name } },
            cancellationToken);
    }

    private static void RequireFile(IEnumerable<McsvFileEntry> entries, string fileName)
    {
        if (!entries.Any(entry => entry.IsFile && entry.Name.Equals(fileName, StringComparison.Ordinal)))
            throw new McsvApiException("Expected add-on archive was not found after extraction: " + fileName);
    }

    private static string ParseLevelName(string serverProperties)
    {
        using var reader = new StringReader(serverProperties ?? string.Empty);
        while (reader.ReadLine() is { } line)
        {
            var trimmed = line.Trim();
            if (trimmed.StartsWith("#", StringComparison.Ordinal) || !trimmed.StartsWith("level-name=", StringComparison.OrdinalIgnoreCase))
                continue;
            return trimmed.Substring("level-name=".Length).Trim();
        }
        return string.Empty;
    }

    private static string BuildPluginConfig(
        string relayWebSocket,
        IReadOnlyList<string> backupRelays,
        string serverId,
        string bridgeSecret)
    {
        if (!Uri.TryCreate(relayWebSocket, UriKind.Absolute, out var relayUri) ||
            (relayUri.Scheme != "ws" && relayUri.Scheme != "wss"))
            throw new McsvApiException("Render Relay WebSocket URL is invalid.");
        if (string.IsNullOrWhiteSpace(serverId))
            throw new McsvApiException("Server ID is required.");
        if (string.IsNullOrWhiteSpace(bridgeSecret) || bridgeSecret.Length < 16)
            throw new McsvApiException("Bridge Secret must contain at least 16 characters.");

        var backups = backupRelays
            .Where(value => !string.IsNullOrWhiteSpace(value))
            .Select(value => "\"" + Toml(value.Trim()) + "\"");

        var sb = new StringBuilder();
        sb.AppendLine("[tracking]");
        sb.AppendLine("interval_ticks = 2");
        sb.AppendLine("position_epsilon = 0.05");
        sb.AppendLine("rotation_epsilon = 1.0");
        sb.AppendLine("log_position_changes = false");
        sb.AppendLine("heartbeat_seconds = 30");
        sb.AppendLine();
        sb.AppendLine("[binding]");
        sb.AppendLine("min_key_length = 4");
        sb.AppendLine("max_key_length = 128");
        sb.AppendLine();
        sb.AppendLine("[voice_range]");
        sb.AppendLine("default_blocks = 20");
        sb.AppendLine("max_blocks = 150");
        sb.AppendLine();
        sb.AppendLine("[bridge]");
        sb.AppendLine("enabled = true");
        sb.AppendLine($"url = \"{Toml(relayWebSocket)}\"");
        sb.AppendLine("backup_urls = [" + string.Join(", ", backups) + "]");
        sb.AppendLine($"server_id = \"{Toml(serverId.Trim())}\"");
        sb.AppendLine($"secret = \"{Toml(bridgeSecret.Trim())}\"");
        sb.AppendLine("reconnect_seconds = 5");
        sb.AppendLine("max_attempts = 5");
        sb.AppendLine("peer_timeout_seconds = 30");
        return sb.ToString();
    }

    private static string Toml(string value) =>
        (value ?? string.Empty)
            .Replace("\\", "\\\\", StringComparison.Ordinal)
            .Replace("\"", "\\\"", StringComparison.Ordinal)
            .Replace("\r", string.Empty, StringComparison.Ordinal)
            .Replace("\n", string.Empty, StringComparison.Ordinal);

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

    private static string SafeMessage(Exception exception)
    {
        var message = exception.Message ?? string.Empty;
        return message.Length <= 240 ? message : message[..240];
    }

    private sealed record McsvFileEntry(string Name, bool IsFile);
}
