#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import sys


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count == 0:
        if new in text:
            return text
        raise RuntimeError(f"Voice range patch anchor missing: {label}")
    if count != 1:
        raise RuntimeError(f"Voice range patch anchor not unique ({count}): {label}")
    return text.replace(old, new, 1)


def patch_android_bridge(root: Path) -> Path:
    path = root / "VoiceCraft.Server.Android" / "EndstoneBridgeController.cs"
    text = path.read_text(encoding="utf-8")

    text = replace_once(
        text,
        '    private const string ItemMicMutedProperty = "voicecraft:item_mic_muted";\n',
        '    private const string ItemMicMutedProperty = "voicecraft:item_mic_muted";\n'
        '    private const string ProximityMinRangeProperty = "ProximityEffect:MinRange";\n'
        '    private const string ProximityMaxRangeProperty = "ProximityEffect:MaxRange";\n'
        '    private const float DefaultVoiceRange = 20f;\n'
        '    private const float VoiceRangeFadeStartRatio = 0.50f;\n',
        "voice range property constants",
    )

    text = replace_once(
        text,
        '        entity.SetProperty(ItemMicMutedProperty, false);\n'
        '        entity.SetDescription($"Welcome! Your binding key is {key}");\n',
        '        entity.SetProperty(ItemMicMutedProperty, false);\n'
        '        entity.SetProperty<float?>(ProximityMinRangeProperty, DefaultVoiceRange * VoiceRangeFadeStartRatio);\n'
        '        entity.SetProperty<float?>(ProximityMaxRangeProperty, DefaultVoiceRange);\n'
        '        entity.SetDescription($"Welcome! Your binding key is {key}");\n',
        "reset voice range and fade on recycled entity",
    )

    mic_block_tail = (
        '            }\n'
        '        }\n'
        '    }\n\n'
        '    private void HandleBind(BridgeBindRequest request)\n'
    )
    range_block_tail = (
        '            }\n'
        '        }\n\n'
        '        // Per-player outgoing microphone range. Keep full volume through 50%\n'
        '        // of the selected range, then let VoiceCraft ProximityEffect fade\n'
        '        // from full volume to silence over the final 50%.\n'
        '        if (state.VoiceRange.HasValue)\n'
        '        {\n'
        '            var voiceRange = Math.Clamp(state.VoiceRange.Value, 1f, 30_000_000f);\n'
        '            var fadeStart = Math.Clamp(voiceRange * VoiceRangeFadeStartRatio, 0f, voiceRange);\n'
        '            entity.SetProperty<float?>(ProximityMinRangeProperty, fadeStart);\n'
        '            entity.SetProperty<float?>(ProximityMaxRangeProperty, voiceRange);\n'
        '        }\n'
        '    }\n\n'
        '    private void HandleBind(BridgeBindRequest request)\n'
    )
    text = replace_once(text, mic_block_tail, range_block_tail, "apply voice range distance fade to entity")

    text = replace_once(
        text,
        '        float Pitch,\n        bool? MicOn)\n',
        '        float Pitch,\n        bool? MicOn,\n        float? VoiceRange)\n',
        "BridgePlayerState VoiceRange field",
    )

    parser_old = (
        '            bool? micOn = null;\n'
        '            if (root.TryGetProperty("micOn", out var micElement) &&\n'
        '                micElement.ValueKind is JsonValueKind.True or JsonValueKind.False)\n'
        '                micOn = micElement.GetBoolean();\n\n'
        '            state = new BridgePlayerState(name, xuid, uuid, dimension, x, y, z, yaw, pitch, micOn);\n'
    )
    parser_new = (
        '            bool? micOn = null;\n'
        '            if (root.TryGetProperty("micOn", out var micElement) &&\n'
        '                micElement.ValueKind is JsonValueKind.True or JsonValueKind.False)\n'
        '                micOn = micElement.GetBoolean();\n\n'
        '            float? voiceRange = null;\n'
        '            if (root.TryGetProperty("voiceRange", out var rangeElement) &&\n'
        '                rangeElement.ValueKind == JsonValueKind.Number &&\n'
        '                rangeElement.TryGetSingle(out var parsedRange) &&\n'
        '                float.IsFinite(parsedRange) && parsedRange >= 1f)\n'
        '                voiceRange = Math.Clamp(parsedRange, 1f, 30_000_000f);\n\n'
        '            state = new BridgePlayerState(name, xuid, uuid, dimension, x, y, z, yaw, pitch, micOn, voiceRange);\n'
    )
    text = replace_once(text, parser_old, parser_new, "parse voiceRange extension")

    text = text.replace('bridgeVersion = "0.2.6"', 'bridgeVersion = "0.2.8"')
    path.write_text(text, encoding="utf-8")

    final = path.read_text(encoding="utf-8")
    required = [
        'ProximityMinRangeProperty = "ProximityEffect:MinRange"',
        'ProximityMaxRangeProperty = "ProximityEffect:MaxRange"',
        "VoiceRangeFadeStartRatio = 0.50f",
        "float? VoiceRange",
        'root.TryGetProperty("voiceRange"',
        "state.VoiceRange.HasValue",
        "voiceRange * VoiceRangeFadeStartRatio",
        "entity.SetProperty<float?>(ProximityMinRangeProperty, fadeStart)",
        "entity.SetProperty<float?>(ProximityMaxRangeProperty, voiceRange)",
        'bridgeVersion = "0.2.8"',
    ]
    missing = [value for value in required if value not in final]
    if missing:
        raise RuntimeError(f"Voice range Android bridge validation failed: {missing}")
    return path


def patch_proximity_effect(root: Path) -> Path:
    path = root / "VoiceCraft.Upstream" / "VoiceCraft.Network" / "Audio" / "Effects" / "ProximityEffect.cs"
    text = path.read_text(encoding="utf-8")

    min_old = '''        public float EvaluateMinRangeProperty(VoiceCraftEntity e1, VoiceCraftEntity e2)\n        {\n            const string property = $"{nameof(ProximityEffect)}:{nameof(MinRange)}";\n            var propVal1 = e1.TryGetProperty<float?>(property, out var prop1);\n            var propVal2 = e2.TryGetProperty<float?>(property, out var prop2);\n            if (!propVal1 && !propVal2) return MinRange;\n            return Math.Min(prop1 ?? float.MaxValue, prop2 ?? float.MaxValue);\n        }\n'''
    min_new = '''        public float EvaluateMinRangeProperty(VoiceCraftEntity e1, VoiceCraftEntity e2)\n        {\n            const string property = $"{nameof(ProximityEffect)}:{nameof(MinRange)}";\n            // VoiceCraft Server Mobile treats MinRange as the source/speaker's\n            // fade-start distance. Listener properties must not change another\n            // player's outgoing attenuation curve.\n            if (!e1.TryGetProperty<float?>(property, out var sourceRange)) return MinRange;\n            return Math.Max(0.0f, sourceRange ?? MinRange);\n        }\n'''
    text = replace_once(text, min_old, min_new, "speaker-only ProximityEffect MinRange")

    max_old = '''        public float EvaluateMaxRangeProperty(VoiceCraftEntity e1, VoiceCraftEntity e2)\n        {\n            const string property = $"{nameof(ProximityEffect)}:{nameof(MaxRange)}";\n            var propVal1 = e1.TryGetProperty<float?>(property, out var prop1);\n            var propVal2 = e2.TryGetProperty<float?>(property, out var prop2);\n            if (!propVal1 && !propVal2) return MaxRange;\n            return Math.Max(prop1 ?? float.MinValue, prop2 ?? float.MinValue);\n        }\n'''
    max_new = '''        public float EvaluateMaxRangeProperty(VoiceCraftEntity e1, VoiceCraftEntity e2)\n        {\n            const string property = $"{nameof(ProximityEffect)}:{nameof(MaxRange)}";\n            // VoiceCraft Server Mobile treats MaxRange as an outgoing speaker\n            // property. e1 is always the source/speaker in VisibilitySystem and\n            // ProximityEffectProcessor, so one loud player cannot expand another\n            // player's microphone range.\n            if (!e1.TryGetProperty<float?>(property, out var sourceRange)) return MaxRange;\n            return Math.Max(0.0f, sourceRange ?? MaxRange);\n        }\n'''
    text = replace_once(text, max_old, max_new, "speaker-only ProximityEffect MaxRange")

    linear_old = '''            var distance = Vector3.Distance(Entity.Position, to.Position) - minRange;\n            var factor = 1f - Math.Clamp(distance / range, 0f, 1f);\n            _lerpVolume.TargetVolume = factor;\n'''
    nonlinear_new = '''            var distance = Vector3.Distance(Entity.Position, to.Position) - minRange;\n            var linearFactor = 1f - Math.Clamp(distance / range, 0f, 1f);\n            // Make the 50%-90% falloff clearly audible without creating a hard cut.\n            // Power 1.5 keeps the fade smooth while reducing distant voices faster.\n            var factor = MathF.Pow(linearFactor, 1.5f);\n            _lerpVolume.TargetVolume = factor;\n'''
    text = replace_once(text, linear_old, nonlinear_new, "strong nonlinear ProximityEffect fade curve")
    path.write_text(text, encoding="utf-8")

    final = path.read_text(encoding="utf-8")
    required = [
        "fade-start distance",
        "Listener properties must not change another",
        "one loud player cannot expand another",
        "50%-90% falloff clearly audible",
        "MathF.Pow(linearFactor, 1.5f)",
        "EvaluateMinRangeProperty",
        "EvaluateMaxRangeProperty",
    ]
    missing = [value for value in required if value not in final]
    if missing:
        raise RuntimeError(f"Voice range ProximityEffect validation failed: {missing}")
    return path


def main() -> None:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
    bridge = patch_android_bridge(root)
    proximity = patch_proximity_effect(root)
    print(f"Applied Voice Range + 50%-100% strong distance fade bridge patch to {bridge}")
    print(f"Applied speaker-only ProximityEffect min/max + nonlinear 1.5 fade curve to {proximity}")


if __name__ == "__main__":
    main()
