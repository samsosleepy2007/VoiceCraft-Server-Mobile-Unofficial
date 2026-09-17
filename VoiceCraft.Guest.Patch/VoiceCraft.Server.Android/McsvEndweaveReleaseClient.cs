using System.Text.Json;
using System.Text.RegularExpressions;

namespace VoiceCraft.Server.Android;

internal sealed record McsvEndweaveReleaseAsset(
    string Name,
    string DownloadUrl,
    string Digest,
    long Size);

internal sealed record McsvEndweaveRelease(
    string Tag,
    Version Version,
    string PyProjectToml,
    IReadOnlyList<McsvEndweaveReleaseAsset> Assets);

internal static class McsvEndweaveReleaseClient
{
    private const string ReleasesUrl =
        "https://api.github.com/repos/EndstoneMC/endweave/releases?per_page=20";
    private const string RawBase =
        "https://raw.githubusercontent.com/EndstoneMC/endweave/";
    private static readonly Regex StableTag = new(
        @"^v?(\d+\.\d+\.\d+)$",
        RegexOptions.Compiled | RegexOptions.CultureInvariant);

    internal static async Task<IReadOnlyList<McsvEndweaveRelease>> GetStableReleasesAsync(
        Action<string>? progress,
        CancellationToken cancellationToken)
    {
        using var http = CreateClient();
        progress?.Invoke("Checking official Endweave releases on GitHub…");

        using var response = await http.GetAsync(ReleasesUrl, cancellationToken);
        if (!response.IsSuccessStatusCode)
            throw new McsvApiException(
                $"GitHub Endweave release lookup failed: HTTP {(int)response.StatusCode}.");

        await using var stream = await response.Content.ReadAsStreamAsync(cancellationToken);
        using var document = await JsonDocument.ParseAsync(stream, cancellationToken: cancellationToken);
        if (document.RootElement.ValueKind != JsonValueKind.Array)
            throw new McsvApiException("GitHub returned an invalid Endweave release list.");

        var discovered = new List<(string Tag, Version Version, List<McsvEndweaveReleaseAsset> Assets)>();
        foreach (var release in document.RootElement.EnumerateArray())
        {
            if (release.ValueKind != JsonValueKind.Object ||
                BoolProperty(release, "draft") ||
                BoolProperty(release, "prerelease"))
                continue;

            var tag = StringProperty(release, "tag_name");
            var match = StableTag.Match(tag);
            if (!match.Success || !Version.TryParse(match.Groups[1].Value, out var version))
                continue;

            var assets = new List<McsvEndweaveReleaseAsset>();
            if (release.TryGetProperty("assets", out var assetArray) &&
                assetArray.ValueKind == JsonValueKind.Array)
            {
                foreach (var asset in assetArray.EnumerateArray())
                {
                    var name = StringProperty(asset, "name");
                    if (!name.EndsWith(".whl", StringComparison.OrdinalIgnoreCase))
                        continue;

                    var downloadUrl = StringProperty(asset, "browser_download_url");
                    var digest = StringProperty(asset, "digest");
                    var size = LongProperty(asset, "size");
                    if (!IsOfficialAssetUrl(downloadUrl, tag, name))
                        continue;

                    assets.Add(new McsvEndweaveReleaseAsset(name, downloadUrl, digest, size));
                }
            }

            if (assets.Count > 0)
                discovered.Add((tag, version, assets));
        }

        var ordered = discovered
            .OrderByDescending(item => item.Version)
            .Take(10)
            .ToArray();

        var result = new List<McsvEndweaveRelease>();
        foreach (var item in ordered)
        {
            cancellationToken.ThrowIfCancellationRequested();
            var metadataUrl = RawBase + Uri.EscapeDataString(item.Tag) + "/pyproject.toml";
            try
            {
                using var metadataResponse = await http.GetAsync(metadataUrl, cancellationToken);
                if (!metadataResponse.IsSuccessStatusCode)
                {
                    progress?.Invoke(
                        $"WARN — Endweave {item.Version} metadata unavailable (HTTP {(int)metadataResponse.StatusCode}); skipping release");
                    continue;
                }

                var pyproject = await metadataResponse.Content.ReadAsStringAsync(cancellationToken);
                if (string.IsNullOrWhiteSpace(pyproject))
                    continue;

                result.Add(new McsvEndweaveRelease(
                    item.Tag,
                    item.Version,
                    pyproject,
                    item.Assets));
            }
            catch (HttpRequestException ex)
            {
                progress?.Invoke(
                    $"WARN — Endweave {item.Version} metadata lookup failed: {ex.Message}");
            }
        }

        if (result.Count == 0)
            throw new McsvApiException(
                "No stable Endweave release with readable official metadata was found on GitHub.");

        progress?.Invoke(
            $"Found {result.Count} stable Endweave release(s); newest is {result[0].Version}");
        return result;
    }

    private static HttpClient CreateClient()
    {
        var handler = new HttpClientHandler
        {
            AllowAutoRedirect = false
        };
        var client = new HttpClient(handler)
        {
            Timeout = TimeSpan.FromSeconds(25)
        };
        client.DefaultRequestHeaders.UserAgent.ParseAdd("VoiceCraft-Server-Mobile/1.7.1");
        client.DefaultRequestHeaders.Accept.ParseAdd("application/vnd.github+json");
        client.DefaultRequestHeaders.Add("X-GitHub-Api-Version", "2022-11-28");
        return client;
    }

    private static bool IsOfficialAssetUrl(string url, string tag, string fileName)
    {
        if (!Uri.TryCreate(url, UriKind.Absolute, out var uri) ||
            !uri.Scheme.Equals("https", StringComparison.OrdinalIgnoreCase) ||
            !uri.Host.Equals("github.com", StringComparison.OrdinalIgnoreCase))
            return false;

        var expected = "/EndstoneMC/endweave/releases/download/" + tag + "/" + fileName;
        return uri.AbsolutePath.Equals(expected, StringComparison.Ordinal);
    }

    private static string StringProperty(JsonElement element, string name)
    {
        if (element.ValueKind == JsonValueKind.Object &&
            element.TryGetProperty(name, out var value) &&
            value.ValueKind == JsonValueKind.String)
            return value.GetString() ?? string.Empty;
        return string.Empty;
    }

    private static bool BoolProperty(JsonElement element, string name) =>
        element.ValueKind == JsonValueKind.Object &&
        element.TryGetProperty(name, out var value) &&
        value.ValueKind == JsonValueKind.True;

    private static long LongProperty(JsonElement element, string name)
    {
        if (element.ValueKind == JsonValueKind.Object &&
            element.TryGetProperty(name, out var value) &&
            value.TryGetInt64(out var number))
            return number;
        return 0;
    }
}
