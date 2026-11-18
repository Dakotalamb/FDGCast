# FDGCast 1.0.5-rc.4 — Stream Doctor PC monitoring preview

The GitHub repository has been renamed from Dakotalamb/ForgeCast to
[Dakotalamb/FDGCast](https://github.com/Dakotalamb/FDGCast). App help, installer,
source links and update-link validation now recognize the new name. Update
validation also accepts existing legacy ForgeCast release-feed links. Internal
module IDs and the existing settings folder stay compatible with upgrades.

## Easier Stream Doctor

The Companion has three prominent whole-PC cards: CPU, GPU and memory. These
are separate from OBS-only CPU usage. The native OBS Doctor dock shows the same
three measurements without requiring another browser preview.

- PC CPU, memory, network and disk counters refresh every three seconds.
- Windows GPU Engine performance counters measure the busiest physical engine
  across adapters; processes using the same physical engine are combined.
  Independent engines and adapters are not added together. Windows counters
  must be supported by the OS, driver and GPU. Unavailable is never shown as 0%.
- Busiest apps refresh every six seconds, with CPU normalized to a share of the
  entire PC. Up to five CPU consumers and five memory consumers are displayed.
- Whole-PC CPU/GPU/memory usage at or above 90% for eight seconds produces a
  resource-pressure warning. OBS rendering and encoding symptoms get a possible
  contributor explanation when simultaneous matching pressure is measured.
- Cards explain what happened and what to try. High usage is evidence of load,
  not proof of a faulty app, driver, or component.
- Process names/PIDs are local display only, excluded from diagnostic exports
  and the OBS bridge. Diagnostic exports include the latest numeric PC sample.
  Paths, command lines and window titles are not collected.

This does not measure VRAM, temperatures, power throttling, driver resets,
individual source/GPU-process cost, per-game FPS, or available internet upload.
Network totals may include virtual interfaces; they are activity, not capacity.
Missing measurements and stream telemetry stay visibly unavailable.

## Stream Optimizer — opt-in for the current stream

Start your stream, open Companion → Stream Doctor, then choose **Optimize this
stream**. On Windows this raises a single OBS process from Normal to Above normal
CPU scheduling priority. It keeps existing custom priority choices. Multiple OBS
instances require the user to close unused instances first. This is a modest
CPU-contention aid, not a promise to optimize every game or fix GPU/network limits.
Game settings and background processes are left alone. There are no security,
service, registry, power-plan, encoder, affinity or bitrate changes.

The UI shows exactly what changed and provides **Restore now**. Restoration
runs when all observed main/additional streams stop, telemetry has been missing
for ten seconds, or Companion closes normally. It is not automatically enabled
for subsequent streams. A restoration journal is written before mutation and
stores PID plus process creation time to avoid touching a reused PID. Later
manual priority changes are preserved. Failed restoration remains visible and
can be retried. On a Companion crash, restoration is retried on its next launch;
closing OBS also clears its temporary process priority. Keep Companion running.

## Preview and validation

This branch includes the branded installer preview. It publishes a new,
non-latest prerelease only after the Windows build and existing checks pass.
It does not replace stable 1.0.4 or change the Hub update feed.

Coverage includes sustained resource-pressure thresholds, physical-engine GPU
aggregation, restoration journal ordering, stop/disconnect/restart recovery,
PID reuse, manual priority changes, failed restoration and demo-mode controls.
Windows build/browser/installer results are recorded by GitHub Actions. A CI VM
may lack physical GPU counters; NVIDIA/AMD/Intel hardware readings and effects
on a live game/stream require real-machine testing. No performance gain is claimed.

## Website builder handoff

- Use https://github.com/Dakotalamb/FDGCast for repository and release links.
- Keep the public stable download/feed on 1.0.4 until stable promotion.
- If listing this preview, label it **1.0.5-rc.4 — PC monitoring preview**.
- Describe CPU/GPU/memory monitoring and optional temporary OBS priority assist.
  Do not advertise guaranteed FPS gains, automatic root-cause detection, thermal
  monitoring, VRAM monitoring or a universal game optimizer.
- Old installed apps only accept the legacy ForgeCast release path or the Hub's
  own HTTPS host. The stable 1.0.4 feed example deliberately keeps the legacy
  release path for these clients. Keep the existing stable feed URLs compatible until clients
  have upgraded to a version that accepts the new FDGCast GitHub path.
- No new Hub endpoints, paid entitlements, or browser permissions are required.
