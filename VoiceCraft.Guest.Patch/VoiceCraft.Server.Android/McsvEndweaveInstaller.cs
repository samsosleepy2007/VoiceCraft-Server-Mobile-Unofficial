namespace VoiceCraft.Server.Android;

internal static class McsvEndweaveInstaller
{
    internal static async Task InstallAsync(
        McsvApiClient api,
        McsvEndweaveWheel wheel,
        Action<string>? progress,
        CancellationToken cancellationToken)
    {
        progress?.Invoke($"Installing Endweave {wheel.Version} ({wheel.PythonTag})…");

        var plugins = await McsvEndweaveSupport.ListAsync(api, "/plugins", cancellationToken);
        var oldWheels = plugins
            .Where(entry => entry.IsFile &&
                (entry.Name.StartsWith("endstone_endweave-", StringComparison.OrdinalIgnoreCase) ||
                 entry.Name.StartsWith("endstone-endweave-", StringComparison.OrdinalIgnoreCase)) &&
                entry.Name.EndsWith(".whl", StringComparison.OrdinalIgnoreCase))
            .Select(entry => entry.Name)
            .Where(name => !name.Equals(wheel.FileName, StringComparison.Ordinal))
            .ToArray();

        if (oldWheels.Length > 0)
        {
            progress?.Invoke("Removing incompatible/older Endweave wheels…");
            await api.CallToolAsync(
                "files_delete",
                new { root = "/plugins", files = oldWheels },
                cancellationToken);
        }

        var refreshed = await McsvEndweaveSupport.ListAsync(api, "/plugins", cancellationToken);
        if (!refreshed.Any(entry => entry.IsFile && entry.Name.Equals(wheel.FileName, StringComparison.Ordinal)))
        {
            await api.CallToolAsync(
                "files_fetch_url",
                new
                {
                    url = wheel.DownloadUrl,
                    directory = "/plugins/",
                    filename = wheel.FileName
                },
                cancellationToken);
        }

        var installed = await McsvEndweaveSupport.ListAsync(api, "/plugins", cancellationToken);
        if (!installed.Any(entry => entry.IsFile && entry.Name.Equals(wheel.FileName, StringComparison.Ordinal)))
            throw new McsvApiException(
                $"Endweave download did not appear in /plugins: {wheel.FileName}");

        progress?.Invoke($"Endweave wheel staged: {wheel.FileName}");
    }
}
