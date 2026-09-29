# Controller Router 0.2.0 candidate review

Reviewed 29 September 2026 against the `dev` branch, including the copies bundled by VirtualGlove and R.O.B. Vision. This is a source and package-readiness review, not a published release or a substitute for live controller acceptance.

## Result

- The reusable Python library, UNO Q portal, console pairing helper, and both product bundles are byte-for-byte synchronized for the shared files.
- The library's declared version and runtime `__version__` now agree at `0.2.0rc2`. The previously published `v0.2.0-rc.1` tag remains historical. The UNO Q portal's `0.3.0` installer version is an independent upgrade-order number.
- All 106 Router tests pass, including pairing, Matrix startup, launch routing, system selection, and browser request checks. The full VirtualGlove and R.O.B. Vision suites also pass in their supported test environments.
- The retired persistent RetroArch writers and merged-gamepad service commands have been removed. Runtime routing supplies session settings; it does not edit a saved `retroarch.cfg`.
- A tracked-filename check found no ROM files, private-key files, or credential files. This is a limited packaging check, not a complete security audit.

## Candidate acceptance still required

1. Build and install the next candidate from the reviewed commit, then repeat an upgrade with each product installation order. Check pairing and saved assignments after both installs.
2. Verify launch, exit, hotkeys, Player 1 and Buddy Player 2 on RetroPie and Batocera. Check a physical controller sleeping and waking during a game.
3. Switch apps on both UNO Qs, confirm the neutral and product Matrix cues, and verify recovery after a reboot and interrupted installer run.
4. Verify downloadable candidate assets and checksums before publishing a final `0.2.0` release.

The previous dated live tests remain evidence for their recorded builds; they do not automatically certify this candidate.
