# Controller Router 0.3.0

Stable release: 14 November 2026. The preceding release was 0.2.0.

## Changes

- Route merged player devices through explicitly registered native RetroPie host adapters, alongside supported RetroArch commands. Daphne adapters include merged input and Select + Start exit handling.
- Include native and custom launch registrations in Players and Systems. **All supported systems, including newly added systems** applies only to supported RetroArch systems and explicitly registered native hosts. Other emulator commands keep their existing controls.
- Preserve original launch arguments, emulator choices, saved controller settings and per-system routing policy. Router does not discover or rewrite arbitrary native emulator configurations.
- Recover an unavailable UNO Q entry page in the background. A healthy page is left running; recovery does not restart Docker, product services or the Matrix app.
- Refresh printable guides, screenshots and integration examples. Add CI for console routing, the UNO Q host and standalone packages, with isolated timer mocks for background-thread tests.

## Optional emulator integrations

- Add opt-in computer input bridges for ArcEm, GSplus and SimCoupe. The ArcEm and GSplus source patches and isolated build helper target the documented upstream revisions; emulator sources, BIOS files and game media are supplied separately. SimCoupe uses its existing named-device support. See [Optional Emulator Adapters](EMULATOR_ADAPTERS.md) for host qualification, dependencies, setup and fallback requirements.
- Register supported existing RetroPie private bridges when their installed commands and registry match. Fresh hosts can qualify an exact original command as a disabled-routing fallback. A passive supervisor can provide the saved physical exit chord for a qualified native fallback without grabbing or forwarding gameplay input. Neither process guesses emulator settings or automatically migrates arbitrary custom launchers.
- The console command-line setup and paired UNO Q Setup > Systems use the shared per-system routing policy. **My existing setup** retains the separately qualified native fallback and its saved controls; it does not create an independent gamepad mapping.

## Version and upgrade boundaries

The reusable library is **0.3.0**; the independent UNO Q runtime installer version is **0.3.3**. The Matrix firmware remains **0.2.0** because its source is unchanged. The runtime version protects the updated portal and Matrix app from replacement by older product bundles carrying runtime 0.3.2 or earlier. Both products must bundle the same shared source.

The Matrix app descriptor does not publish a port through App Lab. The installer and portal reconcile a loopback-only Matrix binding after App Lab starts the app. If an installed product cannot report that its game is idle, automatic recreation is deferred until its status is available; the status recheck reduces, but cannot eliminate, a race with independently started games.

The wheel requires Python 3.10 or newer. Source-based console support on Python 3.7 is covered by the scoped console CI job; this does not claim that the complete UNO Q host or wheel supports Python 3.7.

## UNO Q boot ordering

On verified UNO Q boards with the App Lab system service loaded, the root setup helper installs an ordering-only systemd drop-in so App Lab waits for Arduino's one-shot bootloader writer when both are queued during boot. It installs the rule even if App Lab has not yet added the writer unit. It does not enable the writer, change its completion flag, serialize later manual uploads, or resolve independent flash errors. VirtualGlove root setup runs this helper; R.O.B.-only installation reports the separate administrator command. The original failed first boot overlapped both programmers, but its primary upload error was not retained. A separate flash-write timeout later recovered after a local reset and retry; a general fix for that timeout is not established.

## Validation and remaining acceptance

The final source passed the Router suite, package/import checks, bundled-code synchronization, and CI on both `dev` and `main` across all three projects. Wheel, source, product packages, and printable guide assets were checksum-verified. The Raspberry Pi 4 RetroPie cabinet and both UNO Qs were checked with the final candidate runtime; updated guide assets were delivered separately without changing the installed runtime.

On the cabinet, the owner confirmed controls and exit for ArcEm, GSplus and SimCoupe with Router enabled, and keyboard or mouse controls and exit with **My existing setup** for all three. The owner later reported that the final checklist passed for ArcEm, Apple IIGS Paperboy, SAM Coupé, and the requested VirtualGlove and R.O.B. Vision games on the installed candidate runtime. The preserved Router-off settings do not select independent physical pads for ArcEm or SimCoupe; GSplus has no saved physical pad identity. Paperboy responded normally while Pipe Dream had slow input response, which was not reproduced with Paperboy.

The separate UNO Q running App Lab 0.14.1 exposed a port-format incompatibility, a fresh-install socket-directory race, and a boot-time firmware-upload collision. These were repaired and checked through installation, upgrade, manifest rollback, controlled reboot, Matrix firmware health, and loopback-only port verification. The paired UNO Q was also upgraded and rebooted with Router, Matrix, both products, and saved state healthy. On the cabinet, the owner reported working Router-enabled ArcEm, Apple IIGS Paperboy, and SAM Coupé directions, actions, and exit, plus the requested VirtualGlove and R.O.B. Vision game checks. The release assets and their checksums were validated against the final source revision.

Qualification is specific to the two UNO Qs and RetroPie cabinet recorded above. Fresh installation in both product orders, full system rollback, new pairing and reconnect, and physical behavior on other console platforms were not exercised with the final packages. Saved assignments, game registries, pairing state, and existing emulator controls were preserved in the device checks. No ROMs are distributed.

Use matching product installers. A library wheel alone does not install console services or the UNO Q runtime.
