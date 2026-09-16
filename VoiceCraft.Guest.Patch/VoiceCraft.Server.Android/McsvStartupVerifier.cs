using System.Text.Json;

namespace VoiceCraft.Server.Android;

internal static class McsvStartupVerifier
{
    private static readonly string[] FatalMarkers =
    {
        "InvalidVersion:",
        "not a supported wheel on this platform",
        "PackageNotFoundError: No package metadata was found for endstone-endweave",
        "No package metadata was found for endstone-endweave",
        "No package metadata was found for endstone-voicecraft"
    };

    private static readonly string[] PositiveMarkers =
    {
        "load",
        "loaded",
        "loading",
        "enable",
        "enabled",
        "register",
        "registered",
        "start",
        "started",
        "version"
    };

    internal static async Task VerifyAsync(
        McsvApiClient api,
        Action<string>? progress,
        CancellationToken cancellationToken)
    {
        progress?.Invoke("Checking startup log for Endweave + VoiceCraft…");

        var lastLog = string.Empty;
        for (var attempt = 0; attempt < 8; attempt++)
        {
            cancellationToken.ThrowIfCancellationRequested();
            if (attempt > 0)
                await Task.Delay(TimeSpan.FromSeconds(2), cancellationToken);

            var response = McsvApiClient.UnwrapResult(
                await api.CallToolAsync("logs_startup", cancellationToken: cancellationToken));
            lastLog = FlattenStrings(response);

            foreach (var marker in FatalMarkers)
            {
                if (lastLog.Contains(marker, StringComparison.OrdinalIgnoreCase))
                    throw new McsvApiException(
                        "Startup verification found a Python/plugin error: " + marker);
            }

            var lines = SplitLines(lastLog);
            var endweaveReady = HasPositivePluginLine(lines, "endweave");
            var voiceCraftReady = HasPositivePluginLine(lines, "voicecraft") ||
                                  HasPositivePluginLine(lines, "endstone_voicecraft");

            if (endweaveReady && voiceCraftReady)
            {
                progress?.Invoke("Startup verified — Endweave + VoiceCraft loaded successfully");
                return;
            }
        }

        var endweaveSeen = lastLog.Contains("endweave", StringComparison.OrdinalIgnoreCase);
        var voiceCraftSeen = lastLog.Contains("voicecraft", StringComparison.OrdinalIgnoreCase);
        throw new McsvApiException(
            "Server is Running, but startup logs did not confirm both plugins as loaded. " +
            $"Endweave seen: {endweaveSeen}; VoiceCraft seen: {voiceCraftSeen}. " +
            "Open the MCSV startup log and check plugin loading before retrying.");
    }

    private static bool HasPositivePluginLine(IEnumerable<string> lines, string plugin)
    {
        foreach (var line in lines)
        {
            if (!line.Contains(plugin, StringComparison.OrdinalIgnoreCase))
                continue;

            if (line.Contains("error", StringComparison.OrdinalIgnoreCase) ||
                line.Contains("failed", StringComparison.OrdinalIgnoreCase) ||
                line.Contains("exception", StringComparison.OrdinalIgnoreCase) ||
                line.Contains("not supported", StringComparison.OrdinalIgnoreCase) ||
                line.Contains("not found", StringComparison.OrdinalIgnoreCase))
                continue;

            if (PositiveMarkers.Any(marker =>
                    line.Contains(marker, StringComparison.OrdinalIgnoreCase)))
                return true;

            // Endstone prefixes plugin-owned startup output with the plugin name;
            // a normal non-error plugin line is also accepted as confirmation.
            if (line.Contains("[", StringComparison.Ordinal) &&
                line.Contains("]", StringComparison.Ordinal))
                return true;
        }

        return false;
    }

    private static string[] SplitLines(string value) =>
        (value ?? string.Empty)
            .Replace("\r\n", "\n", StringComparison.Ordinal)
            .Replace('\r', '\n')
            .Split('\n', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries);

    private static string FlattenStrings(JsonElement element)
    {
        var values = new List<string>();
        CollectStrings(element, values);
        return string.Join("\n", values);
    }

    private static void CollectStrings(JsonElement element, List<string> values)
    {
        switch (element.ValueKind)
        {
            case JsonValueKind.String:
                var value = element.GetString();
                if (!string.IsNullOrWhiteSpace(value))
                    values.Add(value);
                break;
            case JsonValueKind.Object:
                foreach (var property in element.EnumerateObject())
                    CollectStrings(property.Value, values);
                break;
            case JsonValueKind.Array:
                foreach (var item in element.EnumerateArray())
                    CollectStrings(item, values);
                break;
        }
    }
}
