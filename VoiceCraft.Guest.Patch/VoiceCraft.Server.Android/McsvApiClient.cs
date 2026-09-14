using System.Net.Http.Headers;
using System.Text;
using System.Text.Json;

namespace VoiceCraft.Server.Android;

internal sealed class McsvApiException : Exception
{
    internal int StatusCode { get; }

    internal McsvApiException(string message, int statusCode = 0)
        : base(message)
    {
        StatusCode = statusCode;
    }
}

internal sealed class McsvApiClient : IDisposable
{
    internal const string ApiBase = "https://api.mcsv.me/api/v1/";
    private readonly HttpClient _http;

    internal McsvApiClient(string apiKey)
    {
        var key = (apiKey ?? string.Empty).Trim();
        if (!key.StartsWith("mcsv_", StringComparison.Ordinal))
            throw new McsvApiException("MCSV API key must start with mcsv_.");

        var handler = new HttpClientHandler
        {
            // Never forward the bearer token through an HTTP redirect.
            AllowAutoRedirect = false
        };
        _http = new HttpClient(handler)
        {
            BaseAddress = new Uri(ApiBase, UriKind.Absolute),
            Timeout = TimeSpan.FromSeconds(45)
        };
        _http.DefaultRequestHeaders.Authorization = new AuthenticationHeaderValue("Bearer", key);
        _http.DefaultRequestHeaders.UserAgent.ParseAdd("VoiceCraft-Server-Mobile/1.7.1");
    }

    internal async Task<JsonElement> ValidateKeyAsync(CancellationToken cancellationToken = default)
    {
        return await SendAsync(HttpMethod.Get, "me", null, cancellationToken);
    }

    internal async Task<HashSet<string>> GetAllowedToolsAsync(CancellationToken cancellationToken = default)
    {
        var root = await SendAsync(HttpMethod.Get, "tools", null, cancellationToken);
        var allowed = new HashSet<string>(StringComparer.Ordinal);
        CollectAllowedTools(root, allowed);
        return allowed;
    }

    internal async Task<JsonElement> CallToolAsync(
        string name,
        object? arguments = null,
        CancellationToken cancellationToken = default)
    {
        if (string.IsNullOrWhiteSpace(name) || name.Any(ch => !(char.IsAsciiLetterOrDigit(ch) || ch == '_')))
            throw new McsvApiException("Invalid MCSV tool name.");

        return await SendAsync(
            HttpMethod.Post,
            "tools/" + name,
            arguments ?? new { },
            cancellationToken);
    }

    internal static JsonElement UnwrapResult(JsonElement root)
    {
        if (root.ValueKind == JsonValueKind.Object &&
            root.TryGetProperty("result", out var result))
            return result.Clone();
        return root.Clone();
    }

    private async Task<JsonElement> SendAsync(
        HttpMethod method,
        string relativePath,
        object? payload,
        CancellationToken cancellationToken)
    {
        using var request = new HttpRequestMessage(method, relativePath);
        if (payload != null)
        {
            request.Content = new StringContent(
                JsonSerializer.Serialize(payload),
                Encoding.UTF8,
                "application/json");
        }

        using var response = await _http.SendAsync(request, cancellationToken);
        var text = await response.Content.ReadAsStringAsync(cancellationToken);

        JsonDocument? document = null;
        try
        {
            if (!string.IsNullOrWhiteSpace(text))
                document = JsonDocument.Parse(text);

            var root = document?.RootElement;
            var okField = root.HasValue && root.Value.ValueKind == JsonValueKind.Object &&
                          root.Value.TryGetProperty("ok", out var okValue)
                ? okValue
                : default;
            var apiSaysNo = okField.ValueKind == JsonValueKind.False;

            if (!response.IsSuccessStatusCode || apiSaysNo)
            {
                var message = root.HasValue ? ExtractError(root.Value) : string.Empty;
                if (string.IsNullOrWhiteSpace(message))
                    message = $"MCSV API request failed ({(int)response.StatusCode}).";
                throw new McsvApiException(message, (int)response.StatusCode);
            }

            if (!root.HasValue)
                throw new McsvApiException("MCSV API returned an empty response.", (int)response.StatusCode);

            return root.Value.Clone();
        }
        catch (JsonException)
        {
            throw new McsvApiException(
                $"MCSV API returned an invalid response ({(int)response.StatusCode}).",
                (int)response.StatusCode);
        }
        finally
        {
            document?.Dispose();
        }
    }

    private static string ExtractError(JsonElement root)
    {
        if (root.ValueKind != JsonValueKind.Object)
            return string.Empty;

        foreach (var key in new[] { "error", "message", "detail" })
        {
            if (root.TryGetProperty(key, out var value) && value.ValueKind == JsonValueKind.String)
                return value.GetString() ?? string.Empty;
        }
        return string.Empty;
    }

    private static void CollectAllowedTools(JsonElement element, HashSet<string> allowed)
    {
        if (element.ValueKind == JsonValueKind.Object)
        {
            if (element.TryGetProperty("name", out var name) &&
                name.ValueKind == JsonValueKind.String &&
                element.TryGetProperty("allowed", out var allowedValue) &&
                allowedValue.ValueKind == JsonValueKind.True)
            {
                var toolName = name.GetString();
                if (!string.IsNullOrWhiteSpace(toolName))
                    allowed.Add(toolName);
            }

            foreach (var property in element.EnumerateObject())
                CollectAllowedTools(property.Value, allowed);
            return;
        }

        if (element.ValueKind == JsonValueKind.Array)
        {
            foreach (var item in element.EnumerateArray())
                CollectAllowedTools(item, allowed);
        }
    }

    public void Dispose() => _http.Dispose();
}
