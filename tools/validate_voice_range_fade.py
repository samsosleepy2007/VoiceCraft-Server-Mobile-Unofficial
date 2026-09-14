#!/usr/bin/env python3
from __future__ import annotations

import math
import sys
from pathlib import Path

FADE_START_RATIO = 0.70


def fade_start(voice_range: float) -> float:
    voice_range = max(1.0, min(30_000_000.0, float(voice_range)))
    return max(0.0, min(voice_range, voice_range * FADE_START_RATIO))


def proximity_gain(distance: float, voice_range: float) -> float:
    maximum = max(1.0, min(30_000_000.0, float(voice_range)))
    minimum = fade_start(maximum)
    if distance <= minimum:
        return 1.0
    if distance >= maximum:
        return 0.0
    return 1.0 - ((distance - minimum) / (maximum - minimum))


def close(actual: float, expected: float, tolerance: float = 1e-6) -> None:
    if not math.isclose(actual, expected, rel_tol=tolerance, abs_tol=tolerance):
        raise AssertionError(f"expected {expected}, got {actual}")


def validate_math() -> None:
    close(fade_start(10), 7.0)
    close(proximity_gain(5, 10), 1.0)
    close(proximity_gain(7, 10), 1.0)
    close(proximity_gain(8.5, 10), 0.5)
    close(proximity_gain(9, 10), 1.0 / 3.0)
    close(proximity_gain(10, 10), 0.0)
    close(proximity_gain(11, 10), 0.0)

    close(fade_start(5), 3.5)
    close(fade_start(20), 14.0)
    close(fade_start(50), 35.0)
    close(fade_start(150), 105.0)

    # Smallest supported range must still have a non-zero fade span.
    close(fade_start(1), 0.7)
    close(proximity_gain(0.85, 1), 0.5)


def validate_sources(root: Path) -> None:
    bridge = (root / "VoiceCraft.Server.Android" / "EndstoneBridgeController.cs").read_text(encoding="utf-8")
    proximity = (
        root
        / "VoiceCraft.Upstream"
        / "VoiceCraft.Network"
        / "Audio"
        / "Effects"
        / "ProximityEffect.cs"
    ).read_text(encoding="utf-8")

    bridge_markers = [
        'ProximityMinRangeProperty = "ProximityEffect:MinRange"',
        'ProximityMaxRangeProperty = "ProximityEffect:MaxRange"',
        'VoiceRangeFadeStartRatio = 0.70f',
        'voiceRange * VoiceRangeFadeStartRatio',
        'SetProperty<float?>(ProximityMinRangeProperty, fadeStart)',
        'SetProperty<float?>(ProximityMaxRangeProperty, voiceRange)',
    ]
    for marker in bridge_markers:
        if marker not in bridge:
            raise AssertionError(f"missing Android fade marker: {marker}")

    proximity_markers = [
        "fade-start distance",
        "Listener properties must not change another",
        "one loud player cannot expand another",
    ]
    for marker in proximity_markers:
        if marker not in proximity:
            raise AssertionError(f"missing ProximityEffect fade marker: {marker}")

    # The patched Min/Max evaluators must no longer read listener properties.
    min_start = proximity.index("public float EvaluateMinRangeProperty")
    max_start = proximity.index("public float EvaluateMaxRangeProperty")
    wet_start = proximity.index("public float EvaluateWetDryProperty")
    min_block = proximity[min_start:max_start]
    max_block = proximity[max_start:wet_start]
    for label, block in (("MinRange", min_block), ("MaxRange", max_block)):
        if "e2.TryGetProperty" in block:
            raise AssertionError(f"{label} still reads listener properties")
        if "e1.TryGetProperty" not in block:
            raise AssertionError(f"{label} is not source/speaker authoritative")


def main() -> None:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
    validate_math()
    validate_sources(root)
    print("Voice Range distance fade validation passed: 70%-100% speaker-only attenuation")


if __name__ == "__main__":
    main()
