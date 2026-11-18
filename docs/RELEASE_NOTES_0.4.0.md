# Controller Router 0.4.0

Release candidate 1: 18 November 2026. The preceding release was 0.3.2.

## Halt the controller when the console shuts down

- Each paired console has a **Halt this controller when the console shuts down** setting in secure Setup. It is off by default, and turning it on or off asks for the Matrix code.
- When it is on, choosing **Shutdown System** in EmulationStation on a RetroPie console asks the UNO Q to halt Linux cleanly. **Quit EmulationStation**, **Restart EmulationStation** and **Restart System** never halt it.
- The console requests a one-time challenge from the UNO Q entry page and signs it with its existing Router connection token under its own `controller-router-halt/1` label; the token is never sent. Each step is bounded, and the console always finishes its own shutdown.
- The UNO Q halts only for a verified request from a console with the setting on, when its halt helper is installed, no product reports a live game, and no other paired console is connected. Each outcome is shown on that console's Setup row.
- A fixed-purpose root helper, `router_shared.uno_halt`, watches one request file and runs `systemctl --no-block halt`. VirtualGlove's root setup installs it; a R.O.B. Vision-only installation prints the combined administrator command with the boot-order helper.
- Halting stops Linux; the board stays powered and starts again only when its power is switched off and on. Batocera and Recalbox consoles, and shutdowns started outside EmulationStation, do not send the request yet.

## Other changes

- Every UNO Q portal page links to **Console setup**, the secure page for paired consoles, access and the halt setting.

## Version and upgrade boundaries

The reusable library is **0.4.0**; the independent UNO Q runtime installer version is **0.4.0**. The Matrix firmware remains **0.2.0**. Product bundles carrying runtime 0.3.5 or earlier cannot replace the updated portal.

## Validation and remaining acceptance

The source passed the Router suite, including tests for the full console-to-UNO halt flow, every refusal, bad, replayed and expired signatures, the root helper's safety checks, and the entry-page relay, plus bundled-code synchronization and the R.O.B. Vision and VirtualGlove suites.

A development build of this source was installed on one RetroPie console and one UNO Q. With the setting off, the console's EmulationStation hook was refused in under a second and the UNO Q kept running. With it on, choosing **Shutdown System** halted the UNO Q through the helper: its record showed the request, its journal reached System Halt with filesystems synced, and it returned with its usual name after power was restored. Batocera, Recalbox, fresh installation in both product orders, and full rollback were not exercised.
