using System.Security.Cryptography;

namespace VoiceCraft.Server.Android;

internal static class McsvEndweaveResolver
{
    private const long MaxWheelBytes = 50L * 1024L * 1024L;

    internal static async Task<McsvEndweaveWheel> ResolveAsync(
        McsvServerEnvironment environment,
        Action<string>? progress,
        CancellationToken cancellationToken)
    {
        Exception? discoveryFailure = null;
        try
        {
            var releases = await McsvEndweaveReleaseClient.GetStableReleasesAsync(
                progress,
                cancellationToken);

            foreach (var release in releases)
            {
                cancellationToken.ThrowIfCancellationRequested();
                if (!McsvEndweaveCompatibility.TryResolveCandidate(
                        release,
                        environment,
                        out var candidate,
                        out var reason) ||
                    candidate == null)
                {
                    progress?.Invoke($"Endweave {release.Version} skipped — {reason}");
                    continue;
                }

                if (!TryParseSha256(candidate.Asset.Digest, out var expectedSha))
                {
                    progress?.Invoke(
                        $"WARN — Endweave {release.Version} asset has no valid GitHub SHA-256 digest; skipping release");
                    continue;
                }

                progress?.Invoke(
                    $"Endweave {release.Version} is compatible: Endstone '{candidate.EndstoneRequirement}', Python '{candidate.PythonRequirement}'");
                await VerifyOfficialAssetAsync(
                    candidate.Asset.DownloadUrl,
                    candidate.Asset.Size,
                    expectedSha,
                    progress,
                    cancellationToken);

                progress?.Invoke(
                    $"Selected official Endweave {release.Version} ({candidate.PythonTag}); SHA-256 verified");
                return new McsvEndweaveWheel(
                    release.Version.ToString(),
                    candidate.Asset.Name,
                    candidate.Asset.DownloadUrl,
                    expectedSha,
                    environment.OperatingSystem,
                    environment.Architecture,
                    candidate.PythonTag);
            }
        }
        catch (OperationCanceledException)
        {
            throw;
        }
        catch (Exception ex) when (ex is HttpRequestException or TaskCanceledException or McsvApiException)
        {
            discoveryFailure = ex;
            progress?.Invoke(
                "WARN — dynamic Endweave release resolution failed; checking last-known-good fallback");
        }

        McsvEndweaveWheel fallback;
        try
        {
            fallback = McsvEndweaveCatalog.SelectWheel(environment);
        }
        catch (Exception fallbackError)
        {
            var detail = discoveryFailure == null
                ? "No compatible official Endweave release was found."
                : "Dynamic lookup failed: " + SafeMessage(discoveryFailure) + ".";
            throw new McsvApiException(
                detail + " Last-known-good fallback is also incompatible: " + SafeMessage(fallbackError));
        }

        progress?.Invoke(
            $"WARN — using last-known-good Endweave {fallback.Version} after compatibility checks");
        await VerifyOfficialAssetAsync(
            fallback.DownloadUrl,
            0,
            fallback.Sha256,
            progress,
            cancellationToken);
        progress?.Invoke(
            $"Fallback Endweave {fallback.Version} SHA-256 verified");
        return fallback;
    }

    private static async Task VerifyOfficialAssetAsync(
        string downloadUrl,
        long expectedSize,
        string expectedSha256,
        Action<string>? progress,
        CancellationToken cancellationToken)
    {
        if (!Uri.TryCreate(downloadUrl, UriKind.Absolute, out var uri) ||
            !uri.Scheme.Equals("https", StringComparison.OrdinalIgnoreCase) ||
            !uri.Host.Equals("github.com", StringComparison.OrdinalIgnoreCase) ||
            !uri.AbsolutePath.StartsWith(
                "/EndstoneMC/endweave/releases/download/",
                StringComparison.Ordinal))
            throw new McsvApiException("Refused a non-official Endweave download URL.");

        if (expectedSize < 0 || expectedSize > MaxWheelBytes)
            throw new McsvApiException(
                $"Endweave wheel size is outside the allowed range: {expectedSize} bytes.");

        if (!IsSha256(expectedSha256))
            throw new McsvApiException("Endweave SHA-256 digest is invalid.");

        progress?.Invoke("Verifying official Endweave wheel SHA-256…");
        using var handler = new HttpClientHandler
        {
            AllowAutoRedirect = true,
            MaxAutomaticRedirections = 5
        };
        using var http = new HttpClient(handler)
        {
            Timeout = TimeSpan.FromSeconds(45)
        };
        http.DefaultRequestHeaders.UserAgent.ParseAdd("VoiceCraft-Server-Mobile/1.7.1");

        using var response = await http.GetAsync(
            downloadUrl,
            HttpCompletionOption.ResponseHeadersRead,
            cancellationToken);
        if (!response.IsSuccessStatusCode)
            throw new McsvApiException(
                $"Could not verify Endweave wheel: HTTP {(int)response.StatusCode}.");

        var contentLength = response.Content.Headers.ContentLength;
        if (contentLength.HasValue && contentLength.Value > MaxWheelBytes)
            throw new McsvApiException("Endweave wheel exceeds the 50 MiB verification limit.");
        if (expectedSize > 0 && contentLength.HasValue && contentLength.Value != expectedSize)
            throw new McsvApiException(
                $"Endweave wheel size changed: GitHub API reported {expectedSize}, download returned {contentLength.Value} bytes.");

        await using var stream = await response.Content.ReadAsStreamAsync(cancellationToken);
        using var sha = SHA256.Create();
        var buffer = new byte[64 * 1024];
        long total = 0;
        int read;
        while ((read = await stream.ReadAsync(buffer.AsMemory(0, buffer.Length), cancellationToken)) > 0)
        {
            total += read;
            if (total > MaxWheelBytes)
                throw new McsvApiException("Endweave wheel exceeds the 50 MiB verification limit.");
            sha.TransformBlock(buffer, 0, read, null, 0);
        }
        sha.TransformFinalBlock(Array.Empty<byte>(), 0, 0);

        if (expectedSize > 0 && total != expectedSize)
            throw new McsvApiException(
                $"Endweave wheel size changed while downloading: expected {expectedSize}, got {total} bytes.");

        var actual = Convert.ToHexString(sha.Hash ?? Array.Empty<byte>()).ToLowerInvariant();
        if (!actual.Equals(expectedSha256, StringComparison.OrdinalIgnoreCase))
            throw new McsvApiException(
                $"Endweave SHA-256 verification failed. Expected {expectedSha256}, got {actual}.");
    }

    private static bool TryParseSha256(string digest, out string sha256)
    {
        sha256 = string.Empty;
        var value = (digest ?? string.Empty).Trim();
        const string prefix = "sha256:";
        if (!value.StartsWith(prefix, StringComparison.OrdinalIgnoreCase))
            return false;
        var candidate = value[prefix.Length..].Trim().ToLowerInvariant();
        if (!IsSha256(candidate))
            return false;
        sha256 = candidate;
        return true;
    }

    private static bool IsSha256(string value) =>
        value.Length == 64 && value.All(Uri.IsHexDigit);

    private static string SafeMessage(Exception ex)
    {
        var message = (ex.Message ?? ex.GetType().Name)
            .Replace('\r', ' ')
            .Replace('\n', ' ')
            .Trim();
        return message.Length <= 240 ? message : message[..240];
    }
}
