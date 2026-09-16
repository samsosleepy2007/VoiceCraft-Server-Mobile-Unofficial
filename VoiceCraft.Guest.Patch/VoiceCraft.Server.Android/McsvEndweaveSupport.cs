using System.Text.Json;

namespace VoiceCraft.Server.Android;

internal sealed record McsvEndweavePreflight(
    string ServerName,
    string Game,
    string ServerType,
    string RuntimeRoot);

internal sealed record McsvServerEnvironment(
    string OperatingSystem,
    string Architecture,
    Version PythonVersion,
    string EndstoneRuntimeVersion,
    string RuntimePath,
    string SitePackagesPath)
{
    internal string Summary =>
        $"{OperatingSystem} {Architecture} • Python {PythonVersion.Major}.{PythonVersion.Minor} • Endstone {EndstoneRuntimeVersion}";
}

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

    internal static async Task<McsvServerEnvironment> DetectEnvironmentAsync(
        McsvApiClient api,
        JsonElement serverInfo,
        CancellationToken cancellationToken)
    {
        var runtimeEntries = await ListAsync(api, EndstoneRuntimeRoot, cancellationToken);
        var runtimeCandidates = runtimeEntries
            .Where(entry => !entry.IsFile)
            .Select(entry => new { entry.Name, Version = ParseVersion(entry.Name) })
            .Where(item => item.Version != null)
            .OrderByDescending(item => item.Version)
            .ToArray();

        if (runtimeCandidates.Length == 0)
            throw new McsvApiException(
                "Could not detect an Endstone runtime version under /.endstone-runtime.");

        var runtimeVersion = runtimeCandidates[0].Version!;
        var runtimeName = runtimeCandidates[0].Name;
        var runtimePath = EndstoneRuntimeRoot + "/" + runtimeName;

        var runtimeFiles = await ListAsync(api, runtimePath, cancellationToken);
        if (!runtimeFiles.Any(entry => !entry.IsFile && entry.Name.Equals("lib", StringComparison.Ordinal)))
            throw new McsvApiException(
                $"Unsupported Endstone runtime layout at {runtimePath}; expected a Linux-style lib directory.");

        var libPath = runtimePath + "/lib";
        var libEntries = await ListAsync(api, libPath, cancellationToken);
        var pythonCandidates = libEntries
            .Where(entry => !entry.IsFile && entry.Name.StartsWith("python", StringComparison.OrdinalIgnoreCase))
            .Select(entry => new
            {
                entry.Name,
                Version = ParseVersion(entry.Name["python".Length..])
            })
            .Where(item => item.Version != null && item.Version.Major == 3)
            .OrderByDescending(item => item.Version)
            .ToArray();

        if (pythonCandidates.Length == 0)
            throw new McsvApiException(
                $"Could not detect Python under {libPath}. Endweave requires Python 3.10 or newer.");

        var pythonVersion = pythonCandidates[0].Version!;
        var pythonPath = libPath + "/" + pythonCandidates[0].Name;
        var sitePackagesPath = pythonPath + "/site-packages";
        var pythonEntries = await ListAsync(api, pythonPath, cancellationToken);
        if (!pythonEntries.Any(entry => !entry.IsFile && entry.Name.Equals("site-packages", StringComparison.Ordinal)))
            throw new McsvApiException(
                $"Python site-packages was not found at {sitePackagesPath}.");

        // Endstone's own installed WHEEL metadata is the most reliable fallback
        // when MCSV server_info does not expose host OS/CPU fields. A native
        // Endstone wheel includes tags such as manylinux_*_x86_64.
        var sitePackages = await ListAsync(api, sitePackagesPath, cancellationToken);
        var endstoneDistInfo = sitePackages.FirstOrDefault(entry =>
            !entry.IsFile &&
            entry.Name.StartsWith("endstone-", StringComparison.OrdinalIgnoreCase) &&
            entry.Name.EndsWith(".dist-info", StringComparison.OrdinalIgnoreCase));
        var endstoneWheelMetadata = string.Empty;
        if (endstoneDistInfo != null)
        {
            try
            {
                endstoneWheelMetadata = await ReadTextAsync(
                    api,
                    sitePackagesPath + "/" + endstoneDistInfo.Name + "/WHEEL",
                    cancellationToken);
            }
            catch (McsvApiException)
            {
                // Continue with the other platform signals below. Unknown CPU
                // architecture is still fatal, so this never causes a guess.
            }
        }

        var osHint = FindStringPropertyDeep(
            serverInfo,
            "os",
            "operating_system",
            "platform");
        var operatingSystem = NormalizeOs(osHint);
        if (operatingSystem == "unknown" && !string.IsNullOrWhiteSpace(endstoneWheelMetadata))
            operatingSystem = NormalizeOs(endstoneWheelMetadata);
        if (operatingSystem == "unknown")
            operatingSystem = "linux"; // The validated runtime layout above is Linux-style.

        var archHint = FindStringPropertyDeep(
            serverInfo,
            "architecture",
            "arch",
            "cpu_arch",
            "machine");
        var architecture = NormalizeArchitecture(archHint);

        if (architecture == "unknown" && !string.IsNullOrWhiteSpace(endstoneWheelMetadata))
            architecture = NormalizeArchitecture(endstoneWheelMetadata);

        if (architecture == "unknown")
        {
            foreach (var entry in sitePackages)
            {
                architecture = NormalizeArchitecture(entry.Name);
                if (architecture != "unknown")
                    break;
            }
        }

        if (architecture == "unknown")
            throw new McsvApiException(
                "Could not detect the server CPU architecture from MCSV or Endstone WHEEL metadata. Endweave installation stopped to avoid installing an incompatible native wheel.");

        return new McsvServerEnvironment(
            operatingSystem,
            architecture,
            pythonVersion,
            runtimeVersion.ToString(),
            runtimePath,
            sitePackagesPath);
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

    private static Version? ParseVersion(string value)
    {
        var normalized = (value ?? string.Empty).Trim();
        if (normalized.StartsWith('v') || normalized.StartsWith('V'))
            normalized = normalized[1..];
        return Version.TryParse(normalized, out var version) ? version : null;
    }

    private static string NormalizeOs(string value)
    {
        var normalized = (value ?? string.Empty).Trim().ToLowerInvariant();
        if (normalized.Contains("linux", StringComparison.Ordinal))
            return "linux";
        if (normalized.Contains("windows", StringComparison.Ordinal) ||
            normalized.Contains("win32", StringComparison.Ordinal))
            return "windows";
        return "unknown";
    }

    private static string NormalizeArchitecture(string value)
    {
        var normalized = (value ?? string.Empty).Trim().ToLowerInvariant();
        if (normalized.Contains("x86_64", StringComparison.Ordinal) ||
            normalized.Contains("amd64", StringComparison.Ordinal) ||
            normalized.Equals("x64", StringComparison.Ordinal))
            return "x86_64";
        if (normalized.Contains("aarch64", StringComparison.Ordinal) ||
            normalized.Contains("arm64", StringComparison.Ordinal))
            return "aarch64";
        return "unknown";
    }

    private static string FindStringPropertyDeep(JsonElement element, params string[] names)
    {
        if (element.ValueKind == JsonValueKind.Object)
        {
            foreach (var property in element.EnumerateObject())
            {
                if (names.Any(name => property.Name.Equals(name, StringComparison.OrdinalIgnoreCase)) &&
                    property.Value.ValueKind == JsonValueKind.String)
                    return property.Value.GetString() ?? string.Empty;
            }

            foreach (var property in element.EnumerateObject())
            {
                var nested = FindStringPropertyDeep(property.Value, names);
                if (!string.IsNullOrWhiteSpace(nested))
                    return nested;
            }
        }
        else if (element.ValueKind == JsonValueKind.Array)
        {
            foreach (var item in element.EnumerateArray())
            {
                var nested = FindStringPropertyDeep(item, names);
                if (!string.IsNullOrWhiteSpace(nested))
                    return nested;
            }
        }

        return string.Empty;
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
