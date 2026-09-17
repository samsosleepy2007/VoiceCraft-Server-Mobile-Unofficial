using System.Text.RegularExpressions;

namespace VoiceCraft.Server.Android;

internal sealed record McsvEndweaveCandidate(
    McsvEndweaveRelease Release,
    McsvEndweaveReleaseAsset Asset,
    string PythonTag,
    string EndstoneRequirement,
    string PythonRequirement);

internal static class McsvEndweaveCompatibility
{
    private static readonly Regex RequiresPython = new(
        "(?m)^\\s*requires-python\\s*=\\s*[\"']([^\"']+)[\"']",
        RegexOptions.Compiled | RegexOptions.CultureInvariant);
    private static readonly Regex EndstoneDependency = new(
        "[\"']endstone([^\"']*)[\"']",
        RegexOptions.Compiled | RegexOptions.CultureInvariant | RegexOptions.IgnoreCase);
    private static readonly Regex CpTag = new(
        @"^cp(\d)(\d{1,2})$",
        RegexOptions.Compiled | RegexOptions.CultureInvariant | RegexOptions.IgnoreCase);

    internal static bool TryResolveCandidate(
        McsvEndweaveRelease release,
        McsvServerEnvironment environment,
        out McsvEndweaveCandidate? candidate,
        out string reason)
    {
        candidate = null;

        if (!Version.TryParse(environment.EndstoneRuntimeVersion, out var endstoneVersion))
        {
            reason = "Endstone runtime version could not be parsed";
            return false;
        }

        var pythonRequirement = ExtractRequiresPython(release.PyProjectToml);
        if (string.IsNullOrWhiteSpace(pythonRequirement))
        {
            reason = "release metadata does not declare requires-python";
            return false;
        }
        if (!Satisfies(environment.PythonVersion, pythonRequirement))
        {
            reason = $"Python {MajorMinor(environment.PythonVersion)} does not satisfy '{pythonRequirement}'";
            return false;
        }

        var endstoneRequirement = ExtractEndstoneRequirement(release.PyProjectToml);
        if (string.IsNullOrWhiteSpace(endstoneRequirement))
        {
            reason = "release metadata does not declare an Endstone dependency";
            return false;
        }
        if (!Satisfies(endstoneVersion, endstoneRequirement))
        {
            reason = $"Endstone {environment.EndstoneRuntimeVersion} does not satisfy '{endstoneRequirement}'";
            return false;
        }

        var compatibleAssets = new List<(McsvEndweaveReleaseAsset Asset, string PythonTag, int Score)>();
        foreach (var asset in release.Assets)
        {
            if (TryScoreWheel(asset, release.Version, environment, out var pythonTag, out var score))
                compatibleAssets.Add((asset, pythonTag, score));
        }

        if (compatibleAssets.Count == 0)
        {
            reason = $"no wheel matches {environment.OperatingSystem}/{environment.Architecture}/Python {MajorMinor(environment.PythonVersion)}";
            return false;
        }

        var selected = compatibleAssets
            .OrderByDescending(item => item.Score)
            .ThenBy(item => item.Asset.Name, StringComparer.Ordinal)
            .First();

        candidate = new McsvEndweaveCandidate(
            release,
            selected.Asset,
            selected.PythonTag,
            endstoneRequirement,
            pythonRequirement);
        reason = string.Empty;
        return true;
    }

    internal static string ExtractRequiresPython(string pyproject)
    {
        var match = RequiresPython.Match(pyproject ?? string.Empty);
        return match.Success ? match.Groups[1].Value.Trim() : string.Empty;
    }

    internal static string ExtractEndstoneRequirement(string pyproject)
    {
        foreach (Match match in EndstoneDependency.Matches(pyproject ?? string.Empty))
        {
            var suffix = match.Groups[1].Value.Trim();
            if (suffix.Length == 0)
                return ">=0";
            if (suffix.StartsWith('[', StringComparison.Ordinal))
            {
                var closing = suffix.IndexOf(']');
                suffix = closing >= 0 ? suffix[(closing + 1)..].Trim() : string.Empty;
            }
            if (suffix.StartsWith(';', StringComparison.Ordinal))
                return ">=0";
            return suffix.Length == 0 ? ">=0" : suffix;
        }
        return string.Empty;
    }

    internal static bool Satisfies(Version version, string specifier)
    {
        if (string.IsNullOrWhiteSpace(specifier))
            return true;

        foreach (var rawClause in specifier.Split(',', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries))
        {
            var clause = rawClause.Trim();
            if (clause.Length == 0)
                continue;

            var op = new[] { ">=", "<=", "==", "!=", "~=", ">", "<" }
                .FirstOrDefault(candidate => clause.StartsWith(candidate, StringComparison.Ordinal));
            if (op == null)
                return false;

            var versionText = clause[op.Length..].Trim();
            if (op is "==" or "!=" && versionText.EndsWith(".*", StringComparison.Ordinal))
            {
                var prefix = versionText[..^2];
                var actual = version.ToString();
                var matchesPrefix = actual.Equals(prefix, StringComparison.Ordinal) ||
                    actual.StartsWith(prefix + ".", StringComparison.Ordinal);
                if (op == "==" ? !matchesPrefix : matchesPrefix)
                    return false;
                continue;
            }

            if (!TryParseLooseVersion(versionText, out var required))
                return false;

            var comparison = version.CompareTo(required);
            var satisfied = op switch
            {
                ">=" => comparison >= 0,
                "<=" => comparison <= 0,
                ">" => comparison > 0,
                "<" => comparison < 0,
                "==" => comparison == 0,
                "!=" => comparison != 0,
                "~=" => comparison >= 0 && version < CompatibleUpperBound(required, versionText),
                _ => false
            };
            if (!satisfied)
                return false;
        }

        return true;
    }

    private static bool TryScoreWheel(
        McsvEndweaveReleaseAsset asset,
        Version releaseVersion,
        McsvServerEnvironment environment,
        out string pythonTag,
        out int score)
    {
        pythonTag = string.Empty;
        score = 0;
        var name = asset.Name;
        if (!name.EndsWith(".whl", StringComparison.OrdinalIgnoreCase) ||
            !name.StartsWith($"endstone_endweave-{releaseVersion}-", StringComparison.OrdinalIgnoreCase))
            return false;

        var parts = name.Split('-');
        if (parts.Length < 5)
            return false;

        pythonTag = parts[^3];
        var abiTag = parts[^2];
        var platformTag = parts[^1][..^4];
        if (!PlatformMatches(platformTag, environment))
            return false;

        if (pythonTag.StartsWith("py3", StringComparison.OrdinalIgnoreCase))
        {
            score = 50;
            return environment.PythonVersion.Major == 3;
        }

        var cp = CpTag.Match(pythonTag);
        if (!cp.Success ||
            !int.TryParse(cp.Groups[1].Value, out var major) ||
            !int.TryParse(cp.Groups[2].Value, out var minor) ||
            major != environment.PythonVersion.Major)
            return false;

        if (abiTag.Equals("abi3", StringComparison.OrdinalIgnoreCase))
        {
            if (environment.PythonVersion.Minor < minor)
                return false;
            score = environment.PythonVersion.Minor == minor ? 95 : 80;
            return true;
        }

        if (!abiTag.Equals(pythonTag, StringComparison.OrdinalIgnoreCase))
            return false;
        if (environment.PythonVersion.Minor != minor)
            return false;

        score = 100;
        return true;
    }

    private static bool PlatformMatches(string platformTag, McsvServerEnvironment environment)
    {
        var tag = platformTag.ToLowerInvariant();
        var archMatches = environment.Architecture switch
        {
            "x86_64" => tag.Contains("x86_64", StringComparison.Ordinal) || tag.Contains("amd64", StringComparison.Ordinal),
            "aarch64" => tag.Contains("aarch64", StringComparison.Ordinal) || tag.Contains("arm64", StringComparison.Ordinal),
            _ => false
        };
        if (!archMatches)
            return false;

        return environment.OperatingSystem switch
        {
            "linux" => tag.Contains("manylinux", StringComparison.Ordinal),
            "windows" => tag.Contains("win_", StringComparison.Ordinal),
            _ => false
        };
    }

    private static bool TryParseLooseVersion(string value, out Version version)
    {
        var normalized = (value ?? string.Empty).Trim();
        var plus = normalized.IndexOf('+');
        if (plus >= 0)
            normalized = normalized[..plus];
        var dash = normalized.IndexOf('-');
        if (dash >= 0)
            normalized = normalized[..dash];
        return Version.TryParse(normalized, out version!);
    }

    private static Version CompatibleUpperBound(Version required, string original)
    {
        var components = original.Split('.', StringSplitOptions.RemoveEmptyEntries);
        if (components.Length <= 2)
            return new Version(required.Major + 1, 0);
        return new Version(required.Major, required.Minor + 1);
    }

    private static string MajorMinor(Version version) => $"{version.Major}.{version.Minor}";
}
