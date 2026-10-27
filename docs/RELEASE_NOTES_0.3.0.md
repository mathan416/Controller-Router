# Controller Router 0.3.0

Release preparation: this version has not been published. The latest published Router release remains 0.2.0.

## Changes

- Route merged player devices through explicitly registered native RetroPie host adapters, alongside supported RetroArch commands. Daphne adapters include merged input and Select + Start exit handling.
- Include native and custom launch registrations in Players and Systems. **All supported systems, including newly added systems** applies only to supported RetroArch systems and explicitly registered native hosts. Other emulator commands keep their existing controls.
- Preserve original launch arguments, emulator choices, saved controller settings and per-system routing policy. Router does not discover or rewrite arbitrary native emulator configurations.
- Recover an unavailable UNO Q entry page in the background. A healthy page is left running; recovery does not restart Docker, product services or the Matrix app.
- Refresh printable guides, screenshots and integration examples. Add CI for console routing, the UNO Q host and standalone packages, with isolated timer mocks for background-thread tests.

## Version and upgrade boundaries

The reusable library is **0.3.0**; the independent UNO Q runtime installer version is **0.3.2**. The Matrix firmware remains **0.2.0** because its source is unchanged. The new runtime version protects it from replacement by older product bundles carrying runtime 0.3.1. Both products must bundle the same shared source.

The wheel requires Python 3.10 or newer. Source-based console support on Python 3.7 is covered by the scoped console CI job; this does not claim that the complete UNO Q host or wheel supports Python 3.7.

## Validation and remaining acceptance

The preceding source revision passed all 11 CI jobs across the three projects. Development deployment on the Raspberry Pi 4 RetroPie console verified merged control paths; the UNO Q entry-page recovery check completed in 15.7 seconds without restarting product or Matrix services. Those are scoped development results, not certification of the final downloadable packages or every platform.

Before publication, build from the final committed release revision, verify checksums and bundled guides, and qualify candidate installation, upgrade and rollback on staging hardware in both product installation orders. Keep pairing, saved assignments, game registries and controls through those checks. Game-input, exit and reconnect acceptance must use the candidate's actual platform and emulator. No ROMs are distributed.

Use matching product installers. A library wheel alone does not install console services or the UNO Q runtime.
