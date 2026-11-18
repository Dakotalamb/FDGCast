# Stream Doctor and Windows streaming profile — stable 1.0.5

See [1.0.5 release notes](RELEASE_1.0.5.md) for the current feature list, setup,
restoration behavior, validation and limits. The branded installer and PC monitor
are included in stable 1.0.5; prerelease builds are historical.

## Monitoring

Whole-PC CPU, Windows GPU Engine utilization and system memory are separate from
OBS-only counters. Measurements refresh every three seconds; readable busiest
apps refresh every six. Sustained CPU/GPU/memory usage at or above 90% warns after
eight seconds. GPU process counters are combined per physical engine, with the
busiest engine displayed. Independent engines/adapters are not added together.

Local app names/PIDs are excluded from exported diagnostics and the native OBS
bridge. Numeric measurements are included in reviewed diagnostic exports.
No process paths, command lines or window titles are collected. Network activity
can include virtual interfaces and is not measured internet capacity.

## Temporary settings

Select the options you want while streaming and choose Apply streaming profile.
OBS priority and two desktop-animation preferences can be changed. An existing
High performance power plan and Windows 11 Game Mode preference are optional.
Animations are a minor desktop setting, not a substantial game-performance claim;
power may increase heat/use; Game Mode may need a game restart.

The restoration journal is saved before every attempted change. Startup recovery
accepts legacy priority-only records as well as the new Windows records. Invalid
records block new optimization. PID creation times prevent changing a reused
process; only unchanged applied values are restored, preserving detectably later
manual edits. Partial failures roll back attempted changes in reverse order.

Restores on observed stream stop, ten seconds of telemetry loss, normal server
cleanup, desktop process exit and next launch after a crash. AC-power loss also
ends an active power-plan profile. Keep Companion running; reopen it after a
crash to restore system preferences. Restore now retries failed restorations.

Manual review buttons open Windows recording, Game Mode, startup and notification
settings. They do not silently change those settings or claim to verify them.
No automatic app shutdown, suspension, service disabling, driver, security,
network, audio or game-file changes are made.

## Implementation references

- [SystemParametersInfo](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-systemparametersinfow)
- [Power scheme management](https://learn.microsoft.com/en-us/windows/win32/power/managing-power-schemes)
- [Windows 11 documented Game Mode preference](https://learn.microsoft.com/en-us/windows/apps/develop/settings/settings-windows-11)
- [Windows Settings launch URIs](https://learn.microsoft.com/en-us/windows/apps/develop/launch/launch-settings)

## Website builder handoff

1. Stable version: **1.0.5**, Windows x64 / OBS 32.2.2. Remove preview wording from
   the public current-download card when promoting this release.
2. Repository: https://github.com/Dakotalamb/FDGCast
3. Release: https://github.com/Dakotalamb/FDGCast/releases/tag/v1.0.5
4. Download: https://github.com/Dakotalamb/FDGCast/releases/download/v1.0.5/FDGCast-1.0.5-win-x64-setup.exe
5. Copy the release's actual **latest.json** asset unchanged to the Hub endpoint
   `/fdgcast/releases/latest.json`. It contains the actual binary SHA256 and size.
6. Older installed apps accept the legacy ForgeCast release path or the Hub's own
   HTTPS host. The manifest deliberately retains the legacy path; do not rewrite
   it to the FDGCast path before those clients upgrade. Keep the former repository
   name unused so its release redirects remain intact.
7. Promote whole-PC CPU/GPU/memory monitoring, clearer diagnoses, the selectable
   temporary Windows streaming profile and branded installer. Avoid promises of
   guaranteed FPS, complete root-cause detection, automatic background-app cleanup,
   service disabling, thermal or VRAM monitoring.
8. No new Hub endpoints, permissions, billing or overlay entitlements are needed.
