# Release checks — 29 September 2026

## Scope

Checked Controller Router, VirtualGlove and R.O.B. Vision development checkouts and locally built packages. No release, tag, main merge, deployment, or live service restart was performed. This supplements the earlier code review and deployment reports; it is not a new exhaustive security audit or physical gameplay certification.

## Automated results

| Project | Result |
| --- | --- |
| Controller Router | 101 unittest tests passed |
| R.O.B. Vision | 112 unittest tests passed |
| VirtualGlove | 998 unittest tests completed successfully, including 3 skips |

VirtualGlove initially had three failing checks: a stale review inventory, a Help test expecting its retired pairing URL, and an installer test invoking the shared pairing installer against the host filesystem. Corrected the URL assertion to the shared `/pair` entry, isolated the pairing installer call while checking product registration, and regenerated the review inventory. Shared pairing installation itself remains covered by Router's tests. Also supplied the missing source headers and function documentation required by VirtualGlove's source audit. These corrections remain uncommitted.

VirtualGlove's documentation/PDF audit passed for 25 source guides and corresponding PDF editions. Its source documentation and Engineering Toolkit audits pass. The console recovery suite passed all 15 tests after documentation changes. Shared Router library copies match both product bundles. Whitespace checks pass for all three repositories.

## Packages

- Built and verified a fresh VirtualGlove App Lab ZIP and its UNO Q, RetroPie, Recalbox, Batocera and LaunchBox installer packages. Each includes shared pairing modules; package checksums pass.
- Built a local R.O.B. Vision release package from committed HEAD. Installer assets, PDFs and checksums were generated; checksums pass.
- Built Controller Router's portable Python wheel and verified imports from its extracted contents outside the source checkout.
- Scanned the fresh product source/App Lab archives for ROM file extensions and private SSH key markers: none found. This limited scan does not establish that all possible secrets are absent.
- R.O.B. Vision includes both FCEUmm and Nestopia wrappers for x86_64, x86, aarch64, armv6l, armv7l and riscv64. ELF architecture metadata agrees with the packaged directories. Runtime compatibility on every board has not been revalidated here.

Temporary version strings `v0.1.99-rc.1` and `v0.5.99-rc.1` identify local test packages only. No corresponding Git tags or public releases exist. Builds are under `/tmp/controller-release-check`; R.O.B. Vision's initial test build is under its ignored `output/release` directory.

## Read-only deployment checks

On arduiain.local and virtualglove.local, the Apps API on port 80, shared pairing API on HTTPS 8444, VirtualGlove connection API on 8100 and R.O.B. Vision state API on 8101 each returned HTTP 200 and JSON. The HTTPS smoke client accepted the device certificate for connectivity testing; this does not validate browser certificate trust.

On retropieconsole.local, retropie.local and batocera.local, the shared pairing command is executable and its console service is running. R.O.B. Vision receivers are also running. These checks did not launch games, change saved RetroArch configuration, reset the camera or alter pairings.

## Remaining release gates

1. Commit and rebuild the release-check corrections before creating final candidate artifacts.
2. Install the actual published candidate packages, including repeat upgrades and adding the second product to an existing shared pairing. Validate interrupted-upgrade recovery on a staged device.
3. Repeat reboot recovery and visible gameplay acceptance for both products through their supported console integrations. Confirm Buddy movement, gate response, first input, exit hotkeys and stable controller assignments, including wireless sleep/wake.
4. Confirm camera automatic exposure restoration on hardware configured for automatic exposure. The current unit tests and service availability checks do not establish image brightness after reconnect.
5. Verify the candidate's downloads, browser trust/pairing flow and installed Help/PDF copies. Existing PDF editions passed the documentation audit; no new full-page visual rendering pass was performed in this check.

The automated checks and package builds pass. Final release acceptance remains conditional on the candidate and live checks above.

## Corrected package rebuild

Rebuilt VirtualGlove’s App Lab archive and all installer targets from the corrected working tree, without committing or publishing. The local build is under `/tmp/controller-release-check-corrected`; its build notes record the base commit and pending changes. Package verification and checksum checks passed, and packaged runtime sources match the corrected checkout byte for byte. These are local verification artifacts, not final release candidates. The review inventory, source documentation and whitespace checks also pass. Final candidate packaging remains dependent on a reviewed commit.

## User recovery verification

The user reported that VirtualGlove’s camera behaved correctly after the virtualglove.local reboot. Both RetroPies returned with all controller services active, merged Player 1/2 outputs present, and their shared UNO Q connections Ready. Batocera subsequently returned through mDNS with Router, receivers, game reporting and pairing services running; its shared pairing remains pending. This records reboot availability and the user’s camera observation, not a new complete gameplay endurance test.

## Current software and hourglass deployment

At the user’s request, deployed the current working-tree software to virtualglove.local, arduiain.local, retropieconsole.local, retropie.local and batocera.local. Both UNO Qs compiled and installed the shared Router Matrix sketch. Firmware and host source hashes match the tested checkout; the startup acknowledgement RPC succeeds. Apps and Matrix are ready on both devices, and the saved RetroPie connections returned Connected with both products Ready. Settings/credential checks preserved all 8 protected UNO files on virtualglove.local and all 6 on arduiain.local. The retired VirtualGlove early-start helper is disabled by the shared installer after successful startup.

Console software updates retained protected settings and ownership: 319 files on retropieconsole.local, 79 on retropie.local and 7 on Batocera. Reloaded the updated receiver/game reporting services; Router and receivers are running on all three consoles. Batocera’s menu was reopened and verified running after the controller reload. No Git commit, push, tag or public release was performed. The physical heart-to-hourglass boot sequence still needs the user’s next reboot observation; endpoint acknowledgement is not a photograph of the display. Published-candidate acceptance gates remain applicable.
