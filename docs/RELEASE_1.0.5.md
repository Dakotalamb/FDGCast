# FDGCast 1.0.5

Stable Windows x64 release for the FDGCast OBS plugin and Companion, built against
OBS Studio 32.2.2. Close OBS and Companion before installing. Settings, protected
credentials and existing dock identities are preserved.

## Stream Doctor: your PC as well as OBS

Prominent CPU, GPU and memory cards show whole-PC usage separately from OBS-only
CPU. The native OBS Doctor dock shows the same readings. Expand the busiest-app
list to review CPU/memory consumers and disk/network activity. Warnings explain
what happened and what to try next. Sustained resource pressure can help identify
possible contributors to OBS rendering/encoding lag; it is not proof of a faulty
component or process.

PC readings refresh every three seconds, readable apps every six seconds. GPU
uses Windows GPU Engine counters and reports the busiest physical engine across
adapters; unsupported readings show **Unavailable**. App names stay local and are
excluded from diagnostics and the native bridge. No VRAM, temperatures, driver
faults, per-game FPS or available internet upload-capacity measurement is claimed.

## Stream Optimizer: selectable temporary Windows profile

Start your stream, open Companion → Stream Doctor, choose your options, then
select **Apply streaming profile**:

- **OBS CPU scheduling priority**: Normal → Above normal for a single OBS
  process; existing custom priorities are preserved.
- **Reduced desktop animations**: temporarily disables window minimize/maximize
  and client-area animations. This is a small desktop-overhead change, not a
  promised FPS increase.
- **High performance power plan** (optional): uses an existing plan only while
  plugged-in power is confirmed. May increase heat and power use. Unsupported
  plans are not created or forced.
- **Windows Game Mode preference** (optional, Windows 11): temporarily enables
  the documented per-user preference. Windows may need the game reopened to
  use it; an enabled preference does not prove Game Mode is active for a game.

**Restore now** reverses changes immediately. Restoration also runs when all
observed streams stop, telemetry is absent for ten seconds, or Companion exits.
Loss of confirmed AC power restores the profile when a power-plan change is active.
After a crash, reopen Companion to recover Windows settings; closing OBS alone
clears only its process priority. Later manual changes are preserved where they
can be detected. Failed restoration stays visible and retryable.

Each change has a durable record before it is attempted. Partial failures roll
back completed changes. Invalid recovery records block new optimization rather
than discarding previous restoration data. No profile is enabled automatically
for the next stream. No guaranteed FPS or performance improvement is claimed.

## Guided Windows review

Dedicated buttons open Windows background recording, Game Mode, startup apps and
notification settings. These are **manual review controls**; FDGCast does not
claim to have checked or changed them. Review Windows “Record what happened” if
OBS already handles recording, pause competing downloads/cloud sync in their
apps, and use the measured busiest-app list to decide what to close after saving
work. FPS limiting is suggested when GPU pressure accompanies rendering lag.

The optimizer does not terminate or suspend apps, disable Windows/security/game
services, change antivirus, alter networking/audio/anti-cheat, or modify game,
encoder, bitrate, driver, HAGS or VRAM settings.

## Installer, licensing and repository

The branded charcoal/orange installer is included in this stable release, with
clear welcome/upgrade/progress pages and optional Companion/guide launch choices.
Original GPL licensing and collected dependency notices remain bundled. Core
chat and diagnostics remain free; paid overlay entitlements are unchanged.

The repository is now [Dakotalamb/FDGCast](https://github.com/Dakotalamb/FDGCast).
Installed-client update links keep the legacy ForgeCast release path for
compatibility. Public pages can use the new canonical repository URL.

## Validation and remaining limits

The publication workflow gates this stable release on the Python regression
suite, real Windows animation apply/read/restore tests, power-plan API checks,
frozen PC-monitor/Windows bindings, native OBS compilation, four Chromium UI
suites, real OBS encoded landscape/portrait and canvas checks, packaged dependency
checks, license collection, installer fresh/upgrade walkthrough and installed
OBS-module hash/location checks.

Windows 11 Game Mode registry handling, absent preferences, rollback, failed
restoration, manual changes, AC loss, PID reuse, corrupt journals, authentication
and demo-mode protection are covered by fixtures. The Windows Server CI runner
cannot establish physical NVIDIA/AMD/Intel readings, Game Mode's actual effect on
a running Windows 11 game, thermal behavior or live-account platform delivery.
Check those on the streaming PC; existing platform eligibility/encoder limits
and separately configured Hub integrations still apply.

Release assets include the installer, SHA256SUMS.txt, license texts and the exact
latest.json for the separate Hub's `/fdgcast/releases/latest.json` endpoint.
Publishing this release does not deploy the Hub update feed.
