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
        progress?.Invoke(
            $"Resolver environment — Endstone {environment.EndstoneRuntimeVersion}, Python {environment.PythonVersion.Major}.{environment.PythonVersion.Minor}, {environment.OperatingSystem}/{environment.Architecture}");

        Exception? discoveryFailure = null;
        var officialFailures = new List<string>();
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
                    progress?.Invoke($"COMPAT SKIP — Endweave {release.Version}: {reason}");
                    continue;
                }

                if (!TryParseSha256(candidate.Asset.Digest, out var expectedSha))
                {
                    var failure = $"Endweave {release.Version}: official asset has no valid GitHub SHA-256 digest";
                    officialFailures.Add(failure);
                    progress?.Invoke($"WARN — DIGEST INVALID — {failure}; trying older official release");
                    continue;
                }

                progress?.Invoke(
                    $"COMPAT PASS — Endweave {release.Version}: wheel {candidate.Asset.Name}, Endstone '{candidate.EndstoneRequirement}', Python '{candidate.PythonRequirement}'");

                try
                {
                    await VerifyOfficialAssetAsync(
                        candidate.Asset.DownloadUrl,
                        candidate.Asset.Size,
                        expectedSha,
                        release.Version.ToString(),
                        progress,
                        cancellationToken);
                }
                catch (OperationCanceledException)
                {
                    throw;
                }
                catch (Exception ex) when (ex is HttpRequestException or TaskCanceledException or McsvApiException)
                {
                    var failure = $"Endweave {release.Version}: {SafeMessage(ex)}";
                    officialFailures.Add(failure);
                    progress?.Invoke(
                        $"WARN — official Endweave {release.Version} rejected — {SafeMessage(ex)}; trying older official release");
                    continue;
                }

                progress?.Invoke(
                    $"Selected official Endweave {release.Version} ({candidate.PythonTag}) after compatibility + digest verification");
                return new McsvEndweaveWheel(
                    release.Version.ToString(),
                    candidate.Asset.Name,
                    candidate.Asset.DownloadUrl,
                    expectedSha,
                    environment.OperatingSystem,
                    environment.Architecture,
                    candidate.PythonTag);
            }

            progress?.Invoke(
                "WARN — no verified compatible official Endweave release remained; checking last-known-good fallback");
        }
        catch (OperationCanceledException)
        {
            throw;
        }
        catch (Exception ex) when (ex is HttpRequestException or TaskCanceledException or McsvApiException)
        {
            discoveryFailure = ex;
            progress?.Invoke(
                $"WARN — dynamic Endweave release discovery failed — {SafeMessage(ex)}; checking last-known-good fallback");
        }

        McsvEndweaveWheel fallback;
        try
        {
            fallback = McsvEndweaveCatalog.SelectWheel(environment);
        }
        catch (Exception fallbackError)
        {
            var detail = discoveryFailure == null
                ? "No compatible verified official Endweave release was found."
                : "Dynamic lookup failed: " + SafeMessage(discoveryFailure) + ".";
            if (officialFailures.Count > 0)
                detail += " Official candidates rejected: " + string.Join(" | ", officialFailures.Take(3)) + ".";
            throw new McsvApiException(
                detail + " Last-known-good fallback is also incompatible: " + SafeMessage(fallbackError));
        }

        var fallbackReason = discoveryFailure != null
            ? "official release discovery unavailable"
            : officialFailures.Count > 0
                ? "official candidates failed verification"
                : "no official candidate matched runtime compatibility";
        progress?.Invoke(
            $"WARN — FALLBACK — using last-known-good Endweave {fallback.Version} because {fallbackReason}");

        try
        {
            await VerifyOfficialAssetAsync(
                fallback.DownloadUrl,
                0,
                fallback.Sha256,
                fallback.Version + " fallback",
                progress,
                cancellationToken);
        }
        catch (OperationCanceledException)
        {
            throw;
        }
        catch (Exception ex) when (ex is HttpRequestException or TaskCanceledException or McsvApiException)
        {
            throw new McsvApiException(
                $"Last-known-good Endweave {fallback.Version} failed mandatory digest verification: {SafeMessage(ex)}");
        }

        progress?.Invoke(
            $"FALLBACK PASS — Endweave {fallback.Version} SHA-256 verified");
        return fallback;
    }

    private static async Task VerifyOfficialAssetAsync(
        string downloadUrl,
        long expectedSize,
        string expectedSha256,
        string versionLabel,
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
                $"SIZE INVALID — Endweave wheel size is outside the allowed range: {expectedSize} bytes.");

        if (!IsSha256(expectedSha256))
            throw new McsvApiException("DIGEST INVALID — Endweave SHA-256 digest is invalid.");

        progress?.Invoke(
            $"DIGEST CHECK — Endweave {versionLabel}: SHA-256 {expectedSha256[..12]}…");
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
                $"DOWNLOAD FAIL — Endweave wheel returned HTTP {(int)response.StatusCode}.");

        var contentLength = response.Content.Headers.ContentLength;
        if (contentLength.HasValue && contentLength.Value > MaxWheelBytes)
            throw new McsvApiException("SIZE INVALID — Endweave wheel exceeds the 50 MiB verification limit.");
        if (expectedSize > 0 && contentLength.HasValue && contentLength.Value != expectedSize)
            throw new McsvApiException(
                $"SIZE MISMATCH — GitHub API reported {expectedSize}, download returned {contentLength.Value} bytes.");

        await using var stream = await response.Content.ReadAsStreamAsync(cancellationToken);
        using var sha = SHA256.Create();
        var buffer = new byte[64 * 1024];
        long total = 0;
        int read;
        while ((read = await stream.ReadAsync(buffer.AsMemory(0, buffer.Length), cancellationToken)) > 0)
        {
            total += read;
            if (total > MaxWheelBytes)
                throw new McsvApiException("SIZE INVALID — Endweave wheel exceeds the 50 MiB verification limit.");
            sha.TransformBlock(buffer, 0, read, null, 0);
        }
        sha.TransformFinalBlock(Array.Empty<byte>(), 0, 0);

        if (expectedSize > 0 && total != expectedSize)
            throw new McsvApiException(
                $"SIZE MISMATCH — expected {expectedSize}, downloaded {total} bytes.");

        var actual = Convert.ToHexString(sha.Hash ?? Array.Empty<byte>()).ToLowerInvariant();
        if (!actual.Equals(expectedSha256, StringComparison.OrdinalIgnoreCase))
            throw new McsvApiException(
                $"DIGEST FAIL — expected {expectedSha256}, got {actual}.");

        progress?.Invoke(
            $"DIGEST PASS — Endweave {versionLabel}: SHA-256 verified ({total} bytes)");
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
