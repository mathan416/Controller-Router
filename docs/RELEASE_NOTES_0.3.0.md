# Controller Router 0.3.0

Release preparation: this version has not been published. The latest published Router release remains 0.2.0.

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

The preceding source revision passed all 11 CI jobs across the three projects. Development deployment on the Raspberry Pi 4 RetroPie console verified merged control paths; the UNO Q entry-page recovery check completed in 15.7 seconds without restarting product or Matrix services. Those are scoped development results, not certification of the final downloadable packages or every platform.

On 13 November 2026, the cabinet owner confirmed controls and exit for ArcEm, GSplus and SimCoupe with Router enabled, and keyboard or mouse controls and exit with **My existing setup** for all three. On this cabinet, ArcEm and SimCoupe's preserved native joystick settings do not select independent physical gamepads; GSplus has no saved physical controller identity and observed native selection was R.O.B. Vision Controller 2. Paperboy responded normally while Pipe Dream had slow input response; that game-specific symptom remains uninvestigated. These results cover the cabinet's installed builds and settings, not other installations or all hardware. The paired UNO Q was upgraded to the candidate 0.3.3 portal using its rollback-aware Router portal installer, with the required App Lab base image pre-provisioned from the test UNO Q. Matrix firmware remained 0.2.0; the Matrix endpoint was loopback-only, portal endpoints responded, and 16 protected fingerprints and modes were unchanged. No VirtualGlove or R.O.B. product installer was run on the paired UNO Q; this does not qualify a product-package install or upgrade.

The test UNO Q running App Lab 0.14.1 exposed a port-format incompatibility and a fresh-install socket-directory race. Qualification builds installed R.O.B. Vision followed by VirtualGlove; both were upgraded, the R.O.B. product rollback and VirtualGlove payload transaction rollback were exercised, and Router, Matrix and product endpoints responded. The 0.3.3 no-published-port candidate passed an App Lab restart and a device reboot; the subsequent watchdog lock fix passed an upgrade and App Lab restart. The first reboot after the test device system update failed its firmware upload and required manual local recovery; reliable boot after such a failure is not established. A subsequent upgrade on that test UNO Q used the current capability-based VirtualGlove installer with a qualification snapshot on App Lab CLI and daemon 0.14.1. The owner reported zero failed checks and three actions remaining; independent readback confirmed the staged installer, managed payload and protected state, and the portal and product endpoints responded. This establishes a scoped upgrade result for that device and snapshot, not a released product package, reverse-order clean installation, whole-system rollback, or camera, pairing, reconnect and gameplay acceptance.

Before publication, build from the final committed release revision, verify checksums and bundled guides, and qualify candidate installation, upgrade and rollback on staging hardware in both product installation orders. Keep pairing, saved assignments, game registries and controls through those checks. Game-input, exit and reconnect acceptance must use the candidate's actual platform and emulator. No ROMs are distributed.

Use matching product installers. A library wheel alone does not install console services or the UNO Q runtime.
