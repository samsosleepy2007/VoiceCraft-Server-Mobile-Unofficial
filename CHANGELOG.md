## 2026-09-19 — MCSV Endweave V3.0.2

- Promoted Endstone VoiceCraft **0.2.17** and Item Mic **2.6.10** after in-game validation.
- Added authoritative Bind-state checks, requestId stale-result protection, and clean Settings → disconnect → rebind lifecycle.
- Bind DDUI now closes cleanly on submit; Mic is withheld during Bind and returned after authoritative success.
- Voice Range uses request/ACK/sync state so DDUI values stay consistent with Endstone.
- Android production identity bumped to **version code 22** and the latest release channel now serves the tested 0.2.17/2.6.10 artifacts.

# Changelog

All notable changes to VoiceCraft Server Mobile are recorded here.

The project keeps VoiceCraft upstream pinned to **v1.7.1** while evolving the Android host, Endstone integration, Render relay and user interface around it.

## 2026-09-08 — Endstone 0.2.4 `/vc` control menu

Android companion: `1.7.1-android-phase2-ui4.2` (version code `8`)  
Endstone plugin: `0.2.4`  
Relay protocol: `1`

### Added

- Replaced the four public VoiceCraft slash commands with one player-facing `/vc` command.
- `/vc` opens an Endstone `ActionForm` containing:
  - **Bind Microphone** — opens the Binding Key `ModalForm` and reuses the existing secure bind path.
  - **Cancel Pending Bind** — preserves the old pending-bind cancellation behavior.
  - **Status** — shows relay, binding, dimension, position and tracker state.
  - **Tracked Players (Admin)** — preserves the old operator-only tracked-state view.
- Added direct plugin metadata on the final exported 0.2.4 class.
- Added CI regression guards that verify Endstone sees exactly one public command: `/vc`.

### Fixed

- Fixed the 0.2.2/0.2.3 command-registration regression where Auto Bind, Auto Rebind and tracking worked but `/vcbind`, `/vcunbind`, `/vcstatus` and `/vcdump` disappeared.
- Root cause: Endstone 0.11 constructs Python `PluginDescription` from the exported class `__dict__`; the 0.2.2/0.2.3 entry-point subclasses inherited `commands`/`permissions` instead of declaring them directly.
- 0.2.4 declares `commands`, `permissions`, `api_version`, `prefix`, `description` and `authors` directly on the exported class.

### Changed

- `/vcbind`, `/vcunbind`, `/vcstatus` and `/vcdump` are no longer registered as public slash commands.
- Their existing internal handlers remain in place and are invoked from the `/vc` UI, avoiding duplicated binding/diagnostic logic.

### Preserved

- Automatic join-time Bind form from 0.2.2.
- Automatic 5-second Rebind flow from 0.2.3.
- Stale disconnect-event protection and duplicate rebind suppression.
- Android UI4.2 compatibility.
- Render Relay protocol `1`.
- VoiceCraft v1.7.1 wire/audio protocol.
- Direct LiteNetLib UDP voice path.

### Verification

- PR #11 Endstone CI passed all steps before merge.
- Main Endstone Build #22 passed all steps after merge.
- CI validates Endstone `0.11.10`, `ActionForm`/`ModalForm` availability, final-class metadata ownership, only `/vc` command registration, Auto Bind/Rebind inheritance, strict bridge config, real protocol-1 relay contract, wheel metadata/entrypoint and installed-wheel import.

---

## 2026-09-08 — Android UI4.2 + Endstone 0.2.3

Android version: `1.7.1-android-phase2-ui4.2` (version code `8`)  
Endstone plugin: `0.2.3`  
Relay protocol: `1`

### Added

- Live Android dashboard for Minecraft players, bound/unbound status, entity ID, dimension and position.
- Android `Request Snapshot` action for a fresh Endstone state snapshot.
- Android detects destruction of an already-bound VoiceCraft client entity while its Minecraft player remains online.
- New additive protocol-1 `voice_client_disconnected` control message forwarded through Render.
- Endstone shows a red disconnect warning immediately and reopens the Binding Key form after 5 seconds.
- Duplicate disconnect events are suppressed and manual binding/player quit cancels unnecessary rebind UI.

### Preserved

- VoiceCraft v1.7.1 wire protocol and direct LiteNetLib UDP voice path.
- Render remains control plane only.
- Auto Bind UI on initial join from Endstone 0.2.2.
- Binding Keys and Bridge Secret remain hidden from logs/dashboard.

---

## 2026-09-07 — Endstone 0.2.1 / Android UI4.1 companion release

Endstone plugin: `0.2.1`  
Companion Android release: `1.7.1-android-phase2-ui4.1` (version code `7`)  
Relay protocol: `1`

### Added / hardened

- Added strict bridge configuration validation before opening the Endstone WSS client.
- Relay URL must use `ws://` or `wss://`, include a hostname, use path exactly `/bridge`, and contain no parameters/query/fragment.
- Server ID must be non-empty and at most 100 characters.
- Bridge Secret must be at least 16 characters and placeholder values are rejected.
- Endstone relay hello now advertises `pluginVersion = 0.2.1`.
- Added reconnect-attempt, reconnect-success, WebSocket close-code and transport-error diagnostics without printing the Bridge Secret or binding keys.
- `/vcunbind` wording now explicitly states that it only cancels a pending bind request and does not unbind an already-bound VoiceCraft entity.

### Verification

- Added a real Endstone 0.2.1 ↔ Node Render Relay protocol contract test.
- Verified Endstone authentication / `hello_ok`, Android mock authentication, `peer_status`, `player_state`, `request_snapshot`, `bind`, `bind_result`, Server-ID room isolation, bad-secret rejection with close code `4403`, relay restart, automatic reconnect, and forwarding after reconnect.
- CI verifies Endstone `0.11.10` event-handler annotations, the BDS pre-spawn `Y=32768` filter, package metadata, Endstone entry point, bundled `config.toml`, and installed-wheel import.
- Verified wheel name: `endstone_voicecraft-0.2.1-py3-none-any.whl`.
- No Android wire-protocol change is required; UI4.1 remains compatible with protocol `1`.

---

## 2026-09-07 — Android UI4.1 interaction hotfix

Version: `1.7.1-android-phase2-ui4.1`  
Android version code: `7`

### Fixed

- Fixed the UI4 bug where buttons visibly received touch/press animation but their actual `Click` actions did not run.
- Root cause: the managed .NET for Android `View.Touch` event is generated from a Java listener that returns `bool`; generated `Handled` state defaults to handled unless explicitly changed. The UI4 animation-only touch subscription therefore consumed the gesture before the normal Android `Button` click path could complete.
- The shared `AppButton` wrapper now explicitly sets touch `Handled = false` so animation-only touch listeners do not swallow the gesture.
- Preserved the native Android `OnTouchEvent` / `PerformClick()` path for normal click behavior, accessibility and click sound semantics.

### Diagnostics

- Every native button click now records a `CLICK:` line in Android runtime diagnostics.
- Unexpected exceptions thrown from a button action are caught at the shared button layer and recorded as `ACTION ERROR` with the button label, exception type and message.
- A failed action also shows a user-visible toast instead of silently appearing to do nothing.

### Preserved

- UI4 visual design and layout.
- page/card entrance animation.
- press scale/fade animation.
- haptic feedback.
- Thai / English switching.
- light / dark theme switching.
- required Render Relay startup validation.
- popup navigation to missing configuration.
- Endstone config generator and copy actions.

---

## 2026-09-07 — Android UI4

Version: `1.7.1-android-phase2-ui4`  
Android version code: `6`

### Added

- New soft modern Android launcher inspired by productivity/mobile dashboard design patterns.
- Blue / indigo / white visual system with dark-mode equivalents.
- Gradient server-status hero card.
- Floating rounded bottom navigation.
- Center Start / Stop action in the bottom bar.
- Page fade/slide entrance animation.
- Staggered content entrance animation.
- Button scale/fade interaction feedback.
- Haptic feedback on button actions.
- Input focus animation.
- Server-state pulse animation.
- Cleaner bridge connection-flow cards.
- Automatic diagnostics-help card in Logs.

### Changed

- New `ModernMainActivity` is the launcher.
- UI3 `MainActivity` remains compiled as a disabled fallback/reference.
- Foreground notification now opens the new modern launcher.
- README rewritten to document the actual Phase 2 architecture and previous versions.

### Preserved

- Required Render Relay validation before server startup.
- Thai default language + English switching.
- Light / dark themes.
- Thai-localized logs.
- Render URL → `wss://.../bridge` generation.
- ready-to-paste Endstone config generation.
- error cause/fix diagnostics.
- VoiceCraft v1.7.1 protocol compatibility.

---

## 2026-09-07 — Android UI3

Version: `1.7.1-android-phase2-ui3`  
Android version code: `5`

### Added / Changed

- Render Relay setup became mandatory before VoiceCraft Server startup.
- Startup validation checks port, Render URL, generated WSS URL, Server ID and Bridge Secret.
- Incomplete setup blocks startup before Foreground Service / UDP / TCP are launched.
- Added a second service-side preflight as a safety layer.
- Validation popup lists every missing setting.
- Popup explains where each setting is located and how to fix it.
- “Go to Bridge / Settings” shortcut focuses the affected field.
- Missing/invalid required fields receive red highlights.
- Removed the optional bridge switch because Endstone + Render is now required by this architecture.
- Rebuilt top-bar language/theme/info controls so their touch targets do not overlap.
- Updated interaction handling to normal Android click events with press feedback.

---

## 2026-09-07 — Android UI2

Version: `1.7.1-android-phase2-ui2`  
Android version code: `4`

### Added

- Thai as the default app language.
- Thai / English UI switching.
- Light / dark theme switching.
- Persisted UI language and theme preferences.
- `By SamSoSleepy` branding.
- Button visual feedback.
- Red required-field validation.
- Detailed in-app setup guide.
- Open Render shortcut.
- Thai runtime-log localization.
- Error diagnosis with likely cause and suggested fix.

### Diagnostics covered

- wrong WebSocket `/bridge` path / HTTP 404
- Relay authentication mismatch
- Bridge Secret / Server ID mismatch
- port already in use
- connection refused
- DNS lookup failure
- timeout
- invalid bridge configuration
- unsupported Android runtime API

---

## 2026-09-06 — Android UI1

Version: `1.7.1-android-phase2-modern-ui1`  
Android version code: `3`

### Added

- First modern blue/white card-based Android redesign.
- Home / Bridge / Logs / Settings pages.
- Render Service URL field.
- Automatic `http(s)` → `ws(s)` conversion with required `/bridge` path.
- Copy actions for:
  - LAN IP
  - port
  - IP:port
  - WebSocket URL
  - Bridge Secret
  - VoiceCraft Server Key
  - Endstone plugin config
  - complete bridge setup
- Cryptographically random Bridge Secret generator.
- Secret show/hide controls.
- Ready-to-paste Endstone `config.toml` generator.
- Setup readiness display.

---

## 2026-09-06 — Phase 2 control plane

Endstone plugin version: `0.2.0`

### Endstone

- Outbound authenticated WSS bridge to Render.
- Player create/update/state synchronization.
- XUID, UUID, name, dimension, position, yaw and pitch synchronization.
- `/vcbind` forwarding through the bridge.
- pre-spawn invalid position filtering (`Y=32768`).
- state snapshots and reconnect synchronization.

### Render relay

- Node.js WebSocket relay.
- `BRIDGE_SECRET` authentication.
- room separation by `serverId`.
- Android / Endstone peer-state reporting.
- cached player state replay.
- `/health` endpoint.
- WebSocket forwarding smoke-test CI.

### Android

- Outbound WSS bridge controller.
- VoiceCraft entity creation/update from Endstone player state.
- one-use five-character binding keys.
- binding key displayed through VoiceCraft client description.
- `RuntimeDispatcher` queues network callbacks to the VoiceCraft server tick.
- secrets and binding keys intentionally hidden from runtime logs.

### Important limitation

- Phase 2 solves player-state and binding transport only.
- Voice audio still requires direct LiteNetLib UDP reachability to Android.

---

## 2026-09-06 — Endstone Phase 1

Versions: `0.1.0`, `0.1.1`

### 0.1.0

- Endstone 0.11.x wheel package.
- player join / quit diagnostics.
- scheduler-based player tracking.
- XUID / UUID / dimension / position / rotation capture.
- `/vcbind` and `/vcunbind` command scaffolding.
- `/vcstatus` and operator-only `/vcdump`.
- configurable tracking interval, epsilon and heartbeat.
- binding keys kept in memory and not logged directly.

### 0.1.1

- Fixed Endstone 0.11 runtime event-handler validation by ensuring event annotations are real classes instead of deferred string annotations.
- Real MCSV runtime test confirmed plugin loading, player tracking and commands.

---

## 2026-09-06 — Android Phase 1 and transport stabilization

### Initial Android host

- Native .NET 10 Android ARM64 application.
- VoiceCraft v1.7.1 headless runtime.
- Foreground Service.
- partial wake lock.
- app-private writable storage.
- Start / Stop lifecycle.
- generated/persisted server key.
- UDP voice listener.
- McHttp compatibility transport.

### Headless compatibility fixes

- Patched VoiceCraft server project to build as a reusable library for Android.
- Removed Spectre.Console terminal assumptions in headless Android mode.
- Fixed Android-specific exception / clipboard compile issues.

### Android diagnostics

- Added Runtime / McHttp diagnostic log view.
- Added copy/clear log actions.
- Added local McHttp health/self-probe logging.

### McHttp Android transport

- Found that `HttpListener.Start()` could report success on Android while no usable socket was reachable.
- Replaced Android McHttp with raw `TcpListener` HTTP/1.1 transport.
- Preserved POST-only McHttp semantics, `/connect`, bearer sessions, Z85 body encoding and existing McApi framing.
- Added raw `TcpClient` self-probe.
- Enabled cleartext traffic for LAN McHttp testing.
- Verified LAN TCP reachability to Android from another device.

---

## Upstream

VoiceCraft upstream remains pinned to:

```text
AvionBlock/VoiceCraft
v1.7.1
85aaccccbb58adb23e8c87144e8b1c24bf4b2011
```

Upstream is GPLv3; this derivative project is intended to remain GPL-compatible.
