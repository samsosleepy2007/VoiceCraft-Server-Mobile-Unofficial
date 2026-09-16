namespace VoiceCraft.Server.Android;

internal sealed record McsvEndweaveWheel(
    string Version,
    string FileName,
    string DownloadUrl,
    string Sha256,
    string OperatingSystem,
    string Architecture,
    string PythonTag);

internal static class McsvEndweaveCatalog
{
    internal const string EndweaveVersion = "0.5.1";
    private const string ReleaseBase =
        "https://github.com/EndstoneMC/endweave/releases/download/v0.5.1/";

    internal static McsvEndweaveWheel SelectWheel(McsvServerEnvironment environment)
    {
        if (!Version.TryParse(environment.EndstoneRuntimeVersion, out var endstoneVersion) ||
            endstoneVersion < new Version(0, 11, 0))
            throw new McsvApiException(
                $"Endweave {EndweaveVersion} requires Endstone 0.11 or newer; detected {environment.EndstoneRuntimeVersion}.");

        if (environment.PythonVersion.Major != 3 ||
            environment.PythonVersion.Minor < 10 ||
            environment.PythonVersion.Minor > 14)
            throw new McsvApiException(
                $"Endweave {EndweaveVersion} supports the verified Python range 3.10-3.14; detected {environment.PythonVersion.Major}.{environment.PythonVersion.Minor}.");

        if (!environment.Architecture.Equals("x86_64", StringComparison.Ordinal))
            throw new McsvApiException(
                $"Endweave {EndweaveVersion} does not publish a verified wheel for '{environment.Architecture}' in this installer. Automatic installation stopped.");

        return environment.OperatingSystem switch
        {
            "linux" => SelectLinux(environment.PythonVersion),
            "windows" => SelectWindows(environment.PythonVersion),
            _ => throw new McsvApiException(
                $"Unsupported operating system '{environment.OperatingSystem}' for automatic Endweave installation.")
        };
    }

    private static McsvEndweaveWheel SelectLinux(Version python)
    {
        if (python.Minor == 10)
            return Wheel(
                "endstone_endweave-0.5.1-cp310-cp310-manylinux_2_28_x86_64.whl",
                "8ee90296a782b94fce993bf54b97c5da5a891031bd307c3fe6b7acedf33e47d0",
                "linux",
                "cp310");

        if (python.Minor == 11)
            return Wheel(
                "endstone_endweave-0.5.1-cp311-cp311-manylinux_2_28_x86_64.whl",
                "bbe98c2e2e9d8e81bbe2738fb076036502812c749a1b3a3aee86a9b8c34137b7",
                "linux",
                "cp311");

        return Wheel(
            "endstone_endweave-0.5.1-cp312-abi3-manylinux_2_28_x86_64.whl",
            "3eac84543faaee7bc658a301b1a8ed8b4c147e4eb594065c6e278bbb47596a6c",
            "linux",
            "cp312-abi3");
    }

    private static McsvEndweaveWheel SelectWindows(Version python)
    {
        if (python.Minor == 10)
            return Wheel(
                "endstone_endweave-0.5.1-cp310-cp310-win_amd64.whl",
                "b8ad449e91a2e55733873d1de057d74e45aaa83024efaedd1607615a2968d581",
                "windows",
                "cp310");

        if (python.Minor == 11)
            return Wheel(
                "endstone_endweave-0.5.1-cp311-cp311-win_amd64.whl",
                "a72f132230e5b57db85961fbd28e45faf4f94fc63f5de4154a8347e4dc74441e",
                "windows",
                "cp311");

        return Wheel(
            "endstone_endweave-0.5.1-cp312-abi3-win_amd64.whl",
            "f617dca84d4e624e118221a8eb9d77af73b4114e68dca16609c2652fed10142f",
            "windows",
            "cp312-abi3");
    }

    private static McsvEndweaveWheel Wheel(
        string fileName,
        string sha256,
        string operatingSystem,
        string pythonTag) =>
        new(
            EndweaveVersion,
            fileName,
            ReleaseBase + fileName,
            sha256,
            operatingSystem,
            "x86_64",
            pythonTag);
}
