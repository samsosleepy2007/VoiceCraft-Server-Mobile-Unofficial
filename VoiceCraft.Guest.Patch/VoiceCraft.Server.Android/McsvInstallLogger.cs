using System.Text.RegularExpressions;

namespace VoiceCraft.Server.Android;

internal static class McsvInstallLogger
{
    private static readonly object Sync = new();
    private static readonly Regex McsvTokenPattern = new(
        @"mcsv_[A-Za-z0-9._-]+",
        RegexOptions.Compiled | RegexOptions.CultureInvariant);
    private static readonly Regex BearerPattern = new(
        @"Bearer\s+\S+",
        RegexOptions.Compiled | RegexOptions.CultureInvariant | RegexOptions.IgnoreCase);
    private static readonly Regex SecretAssignmentPattern = new(
        @"(?i)(secret|bridge_secret|token)\s*[:=]\s*[^\s,;]+",
        RegexOptions.Compiled | RegexOptions.CultureInvariant);

    private static int _sessionId;
    private static DateTime _startedAtUtc;
    private static string _lastStep = "not started";

    internal static void Begin()
    {
        int session;
        lock (Sync)
        {
            _sessionId++;
            session = _sessionId;
            _startedAtUtc = DateTime.UtcNow;
            _lastStep = "starting installer";
        }

        AndroidRuntimeLog.Append(
            "MCSV",
            $"INSTALL #{session} START — automatic Endweave + VoiceCraft installation");
    }

    internal static void Progress(string message)
    {
        var safe = Redact(message);
        if (string.IsNullOrWhiteSpace(safe))
            return;

        int session;
        DateTime started;
        lock (Sync)
        {
            session = _sessionId;
            started = _startedAtUtc;
            _lastStep = safe;
        }

        var state = safe.StartsWith("OK", StringComparison.OrdinalIgnoreCase)
            ? "OK"
            : safe.StartsWith("Ready", StringComparison.OrdinalIgnoreCase)
                ? "READY"
                : safe.StartsWith("WARNING", StringComparison.OrdinalIgnoreCase)
                    ? "WARN"
                    : "STEP";

        if (state == "READY")
        {
            var elapsed = started == default
                ? TimeSpan.Zero
                : DateTime.UtcNow - started;
            AndroidRuntimeLog.Append(
                "MCSV",
                $"INSTALL #{session} READY in {elapsed.TotalSeconds:0.0}s — {safe}");
            return;
        }

        AndroidRuntimeLog.Append("MCSV", $"INSTALL #{session} {state} — {safe}");
    }

    internal static void Failure(Exception exception)
    {
        int session;
        string lastStep;
        lock (Sync)
        {
            session = _sessionId;
            lastStep = _lastStep;
        }

        var message = Redact(exception.Message ?? string.Empty);
        if (message.Length > 500)
            message = message[..500];

        AndroidRuntimeLog.Append(
            "MCSV",
            $"INSTALL #{session} ERROR after '{lastStep}' — {exception.GetType().Name}: {message}");

        var hint = ProblemHint(message);
        if (!string.IsNullOrWhiteSpace(hint))
            AndroidRuntimeLog.Append("MCSV", $"INSTALL #{session} HELP — {hint}");
    }

    internal static void Warning(string message)
    {
        int session;
        lock (Sync)
            session = _sessionId;
        AndroidRuntimeLog.Append("MCSV", $"INSTALL #{session} WARN — {Redact(message)}");
    }

    private static string ProblemHint(string message)
    {
        if (message.Contains("Invalid version", StringComparison.OrdinalIgnoreCase) ||
            message.Contains("InvalidVersion", StringComparison.OrdinalIgnoreCase))
            return "Python package metadata is invalid. Repair or remove the broken .dist-info package before retrying.";

        if (message.Contains("not a supported wheel", StringComparison.OrdinalIgnoreCase) ||
            message.Contains("incompatible native wheel", StringComparison.OrdinalIgnoreCase))
            return "The native wheel does not match the server OS, CPU architecture, or Python version.";

        if (message.Contains("PackageNotFoundError", StringComparison.OrdinalIgnoreCase) ||
            message.Contains("No package metadata was found", StringComparison.OrdinalIgnoreCase))
            return "A Python package did not finish installing. Check the wheel selection and the preceding pip error.";

        if (message.Contains("missing required permissions", StringComparison.OrdinalIgnoreCase) ||
            message.Contains("Full access", StringComparison.OrdinalIgnoreCase))
            return "Create an MCSV API key with Full access and retry.";

        if (message.Contains("backup", StringComparison.OrdinalIgnoreCase))
            return "The safety backup gate failed, so installation should stop before changing server files.";

        if (message.Contains("startup", StringComparison.OrdinalIgnoreCase) ||
            message.Contains("Running state", StringComparison.OrdinalIgnoreCase))
            return "The server restarted but post-start verification failed. Check the startup log for Endweave or VoiceCraft load errors.";

        return string.Empty;
    }

    private static string Redact(string value)
    {
        var safe = value ?? string.Empty;
        safe = McsvTokenPattern.Replace(safe, "mcsv_[REDACTED]");
        safe = BearerPattern.Replace(safe, "Bearer [REDACTED]");
        safe = SecretAssignmentPattern.Replace(safe, match =>
        {
            var text = match.Value;
            var separator = text.IndexOfAny(new[] { ':', '=' });
            return separator < 0 ? "[REDACTED]" : text[..(separator + 1)] + " [REDACTED]";
        });
        return safe.Replace("\r", " ", StringComparison.Ordinal)
            .Replace("\n", " ", StringComparison.Ordinal)
            .Trim();
    }
}
