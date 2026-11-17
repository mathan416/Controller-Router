# Controller Router 0.3.1

Release candidate 3: 17 November 2026. The preceding release was 0.3.0.

## Security fixes

- Close a migration loophole in the console link service. The unauthenticated legacy-proof request could be asked to sign a message that `/adopt` accepted as proof of an existing app credential, letting another device on the network take over a console that still had an unmigrated legacy pairing. Legacy-proof nonces must now be lowercase hexadecimal, so that request can no longer produce an adopt proof. The wire format is unchanged and existing UNO Qs remain compatible.
- Require the Matrix confirmation code before secure Setup removes a console or changes an app's access, as pairing already does. Nothing changes until the code shown on the UNO Q Matrix is entered.
- Only the page that opened a Matrix confirmation can cancel it, and a confirmation with the wrong session no longer ends someone else's window or uses up its attempts. A pairing that presents a valid console connection code replaces an unconfirmed Remove or access request instead of waiting behind it.

## Fixes

- When a console connection change fails and the previous connection is restored, the console clears its pending change. Pairing is no longer blocked for two minutes, and services are not restored and restarted a second time.
- Saving and rolling back console assignments both keep R.O.B. Vision's Buddy on Player 2 when R.O.B. Vision is paired.
- Secure Setup and Players and Systems read a saved copy of the connection list, so they no longer wait while the UNO Q checks an unavailable console.
- A full ten-second controller test through a paired console now has time to finish before the UNO Q stops waiting.
- On Recalbox, an idle Router no longer repeats its output setup every second. Hotkeys continue to be resolved for each launch.
- The console Router no longer keeps a CPU core busy. Detecting a running game scans every process, including each installed native host provider, and took about a quarter of a second on a Raspberry Pi; the Router ran it roughly ten times a second. It now checks once a second and rescans only when a process starts or exits, with a periodic full scan. On the tested RetroPie console, detection fell from about 73% to 6% of one core. Installed native host providers are loaded once and reloaded only when their file changes, instead of being re-imported for every scan and every input during a native game. (RC2)
- The console Router no longer re-reads every input device and EmulationStation's controller file each second while idle. It compares a cheap fingerprint of the input devices and controller files, runs discovery and the output index check only when they change or a controller disconnects, and looks again a second later while a new device or game launcher settles. Full safety-net checks now run every 15 seconds. Measured on the tested RetroPie console, the Router's idle work fell from about 19% of one core in RC2 to about 5% (about 75% in RC1). (RC3)
- The `env` and `text` console adapters read their variable name and UNO Q port from the adapter registration. Earlier registrations keep R.O.B. Vision's `ROB_VISION_URL` and port 8766.
- `scripts/sync.py --check` also compares the UNO Q portal's own pairing modules with the library source.

## Version and upgrade boundaries

The reusable library is **0.3.1**; the independent UNO Q runtime installer version is **0.3.4**. The Matrix firmware remains **0.2.0** because its source is unchanged. The runtime version keeps the updated pairing pages from being replaced by product bundles that carry runtime 0.3.3 or earlier. Both products must bundle the same shared source.

The updated Pairing Guide explains the Matrix confirmation for **Disable**, **Enable** and **Remove**.

## Validation and remaining acceptance

The source passed the Router suite, bundled-code synchronization, and the R.O.B. Vision and VirtualGlove suites. The confirmation flow was exercised in a browser against the real pairing page and connection manager with a simulated console and Matrix: pairing, a rejected wrong code, access changes, Remove, and a refused cancel from another browser.

The same source, before these version changes, was installed on one Raspberry Pi RetroPie console and one UNO Q running both products. Every installer check passed, all services started, and the UNO Q reported the console connected with both apps ready after the console rebooted. RC1 was then installed from its published assets with the same results. RC2 was installed from its published assets with the same results, and the RC2 and RC3 idle-loop changes were measured on that console at the Router loop's real cadence before release. Pairing changes on the hardware Matrix and gameplay had not yet been checked when this candidate was prepared; they are required before the stable release.

Use matching product installers. A library wheel alone does not install console services or the UNO Q runtime.
