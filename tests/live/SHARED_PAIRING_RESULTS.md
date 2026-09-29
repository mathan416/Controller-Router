# Shared pairing verification — 29 September 2026

## Automated checks

- Shared Controller Router suite: 98 tests passed, including certificate pinning, bounded requests, code replay and expiry, Matrix attempt limits, per-app revocation, transaction interruption and rollback, independent app installations, legacy identity conflicts, and delayed secure Setup readiness.
- Console pairing suite on RetroPie’s Python 3.7: 11 tests passed.
- R.O.B. Vision installer and release-installer suites: 22 tests passed.
- VirtualGlove scoped receiver/profile and existing pairing compatibility checks: 41 tests passed.
- Desktop and mobile browser fixtures: pairing progression and connection controls worked without script errors or horizontal overflow.
- Shared source and portal copies match between both product repositories. Documentation audit passed; 34 maintained PDFs were rebuilt and rendered for review.

## Live checks

- Both installation orders completed on the UNO Qs: R.O.B. Vision followed by VirtualGlove, and VirtualGlove followed by R.O.B. Vision.
- RetroPie and Batocera shared helpers coexist with VirtualGlove’s registry service. Shared pairing uses port 55359; registry port 55358 remains unchanged.
- Existing RetroPie credentials were authenticated and migrated without entering a new pairing code. One Router connection shows both products Ready with distinct credentials.
- Disabling VirtualGlove left R.O.B. Vision Ready; enabling it again restored VirtualGlove.
- Players and Systems can be read through Router’s authenticated connection.
- Hostname pairing began on both UNO Qs with certificate verification and confirmed Matrix delivery. Cancelling left existing connections unchanged. No physical PIN was read or bypassed.
- Both product services, secure Setup and the shared Matrix were checked after final deployment. Personal settings, Matrix tokens, saved RetroArch checksums and configuration ownership were preserved.
- Conflicting legacy connections on the second UNO Q remain intact and are shown for review.
- Service restarts restored the shared RetroPie connection with both apps Ready, and the UNO Q certificate remained unchanged. The full-device reboot command was refused because passwordless reboot is not authorized; no reboot occurred.

## Remaining acceptance checks

A full-device reboot, a fresh pairing completed by reading the physical Matrix PIN, and actual game input following that pairing still require live confirmation. Recalbox and Windows installation paths have not been validated on hardware in this run. Unit fixtures establish behavior; they do not replace those device checks.
