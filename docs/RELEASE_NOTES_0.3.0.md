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

The reusable library is **0.3.0**; the independent UNO Q runtime installer version is **0.3.2**. The Matrix firmware remains **0.2.0** because its source is unchanged. The new runtime version protects it from replacement by older product bundles carrying runtime 0.3.1. Both products must bundle the same shared source.

The wheel requires Python 3.10 or newer. Source-based console support on Python 3.7 is covered by the scoped console CI job; this does not claim that the complete UNO Q host or wheel supports Python 3.7.

## Validation and remaining acceptance

The preceding source revision passed all 11 CI jobs across the three projects. Development deployment on the Raspberry Pi 4 RetroPie console verified merged control paths; the UNO Q entry-page recovery check completed in 15.7 seconds without restarting product or Matrix services. Those are scoped development results, not certification of the final downloadable packages or every platform.

On 13 November 2026, the cabinet owner confirmed controls and exit for ArcEm, GSplus and SimCoupe with Router enabled, and keyboard or mouse controls and exit with **My existing setup** for all three. On this cabinet, ArcEm and SimCoupe's preserved native joystick settings do not select independent physical gamepads; GSplus has no saved physical controller identity and observed native selection was R.O.B. Vision Controller 2. Paperboy responded normally while Pipe Dream had slow input response; that game-specific symptom remains uninvestigated. These results cover the cabinet's installed builds and settings, not other installations or all hardware. The live paired UNO Q portal listed the three systems and its web and pairing endpoints responded, but this is not candidate-package install and upgrade acceptance.

Before publication, build from the final committed release revision, verify checksums and bundled guides, and qualify candidate installation, upgrade and rollback on staging hardware in both product installation orders. Keep pairing, saved assignments, game registries and controls through those checks. Game-input, exit and reconnect acceptance must use the candidate's actual platform and emulator. No ROMs are distributed.

Use matching product installers. A library wheel alone does not install console services or the UNO Q runtime.
