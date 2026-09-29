# Deployment review — 29 September 2026

## Repairs

- Installed the previously missing shared pairing service and `pair-console` helper on retropieconsole.local; registered both installed apps.
- Synchronized current shared Router modules in both product installations and the separate launch library on all three consoles.
- Preserved saved RetroArch files and ownership. Recursive saved-config comparisons were made during repair; the final inventory also matched the initial top-level system-config inventory.
- Existing retropieconsole.local pairing imported into virtualglove.local with both apps Ready and no conflicts. arduiain.local retained retropie.local with both apps Ready.

## Verification

- All 101 Controller Router automated tests passed.
- Eleven console pairing tests passed on each RetroPie.
- All three real console pairing commands executed successfully. Each console hostname and TLS-bound code was accepted by the UNO Q, and the Matrix confirmation start acknowledged delivery. Each test was cancelled before confirmation; existing credentials were not replaced by test pairing.
- Both UNO Qs responded at Apps, VirtualGlove, R.O.B. Vision, secure Setup, and Matrix health endpoints. Active Router source files matched the canonical source.
- RetroPie pairing, Router, game-registry, and both receiver services were active. Batocera shared pairing and VirtualGlove services were enabled, with both receivers running.

## Recoverable cleanup

Only known transfer artifacts and isolated test work were archived, after checking service/configuration references, process command lines, and Docker metadata. Installed apps, settings, ROMs, emulator binaries, and existing backups were excluded.

| Device | Items archived | Archive |
|---|---:|---|
| retropieconsole.local | 3 | `/home/pi/.local/state/controller-maintenance/retired-deployment-files-1790693634` |
| retropie.local | 12 | `/home/pi/.local/state/controller-maintenance/retired-deployment-files-1790693648` |
| batocera.local | 14 | `/userdata/system/.local/state/controller-maintenance/retired-deployment-files-1790693649` |
| virtualglove.local | 15 | `/home/arduino/.local/state/controller-maintenance/retired-deployment-files-1790693650` |
| arduiain.local | 20 | `/home/arduino/.local/state/controller-maintenance/retired-deployment-files-1790693654` |

Each archive contains a manifest of original paths. No permanent cleanup deletions were performed.

## Limits

No fresh gameplay, physical-controller sleep/wake, reboot, or visual inspection of the LEDs was performed during this deployment review. Matrix delivery was acknowledged by firmware; the six-digit sequence still requires an on-device visual check. Batocera pairing was tested through start/cancel rather than completing a new connection. Existing console relationships were preserved.

No commits, pushes, or releases were made.
