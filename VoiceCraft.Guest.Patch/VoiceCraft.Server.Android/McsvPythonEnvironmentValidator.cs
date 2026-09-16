namespace VoiceCraft.Server.Android;

internal static class McsvPythonEnvironmentValidator
{
    internal static async Task ValidateAsync(
        McsvApiClient api,
        McsvServerEnvironment environment,
        Action<string>? progress,
        CancellationToken cancellationToken)
    {
        progress?.Invoke("Checking Python package metadata…");

        var entries = await McsvEndweaveSupport.ListAsync(
            api,
            environment.SitePackagesPath,
            cancellationToken);

        var distInfos = entries
            .Where(entry => !entry.IsFile &&
                entry.Name.EndsWith(".dist-info", StringComparison.OrdinalIgnoreCase))
            .OrderBy(entry => entry.Name, StringComparer.OrdinalIgnoreCase)
            .ToArray();

        foreach (var distInfo in distInfos)
        {
            cancellationToken.ThrowIfCancellationRequested();
            var metadataPath = environment.SitePackagesPath + "/" + distInfo.Name + "/METADATA";
            string metadata;
            try
            {
                metadata = await McsvEndweaveSupport.ReadTextAsync(api, metadataPath, cancellationToken);
            }
            catch (McsvApiException ex)
            {
                throw new McsvApiException(
                    $"Python package metadata could not be read: {distInfo.Name}/METADATA. " +
                    "Repair or remove the broken package before installing VoiceCraft/Endweave. " + ex.Message,
                    ex.StatusCode);
            }

            var packageName = Header(metadata, "Name");
            var version = Header(metadata, "Version");
            if (string.IsNullOrWhiteSpace(packageName))
                packageName = distInfo.Name[..^".dist-info".Length];

            if (!LooksLikePep440Version(version))
                throw new McsvApiException(
                    $"Python package metadata is invalid: '{packageName}' has Version '{version}'. " +
                    $"Problem file: {metadataPath}. Fix this package before continuing; pip will fail while this metadata is installed.");
        }
    }

    private static string Header(string metadata, string name)
    {
        using var reader = new StringReader(metadata ?? string.Empty);
        var prefix = name + ":";
        while (reader.ReadLine() is { } line)
        {
            if (line.StartsWith(prefix, StringComparison.OrdinalIgnoreCase))
                return line[prefix.Length..].Trim();
            if (line.Length == 0)
                break;
        }
        return string.Empty;
    }

    private static bool LooksLikePep440Version(string version)
    {
        if (string.IsNullOrWhiteSpace(version) ||
            version.Any(char.IsWhiteSpace) ||
            version.Contains('/') ||
            version.Contains('\\'))
            return false;

        var value = version.Trim();
        var index = value.StartsWith('v') || value.StartsWith('V') ? 1 : 0;
        if (index >= value.Length || !char.IsDigit(value[index]))
            return false;

        // This is intentionally conservative rather than a complete PEP 440 parser.
        // pip-invalid metadata seen in the field (for example
        // "mumble-bridge-0.1.0") is rejected because it does not start with a
        // numeric version. Valid numeric releases, pre-releases, epochs, post/dev
        // releases and local versions continue through to pip/Endstone.
        return true;
    }
}
