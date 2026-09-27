# Controller Router library

Shared, dependency-free Linux controller routing for maker projects. It discovers EmulationStation gamepads, persists stable Player 1–4 assignments, combines physical and virtual inputs into uinput gamepads, and maps those outputs into RetroArch.

## UNO Q controller launcher

The installer makes Controller Router the App Lab startup app on initial and
repeat installs, even if another app was previously selected.

The `uno_portal` package is the shared UNO Q entry page and Matrix owner for VirtualGlove and R.O.B. Vision. Both installers bundle the same versioned package. It owns port 80; VirtualGlove's browser uses port 8100 and R.O.B. Vision's uses 8101. VirtualGlove secure pairing remains on 8443, and R.O.B. Vision's console receiver remains on 8766. A registered game session automatically selects its controller and returns Router to neutral when it ends; no browser is required for game input. With one controller installed, opening the UNO Q address selects and opens it. With both installed, the page lets a user choose. A direct top-level visit to either product's browser port selects that product too. Manual selection is blocked during a live game.

Controller Router owns the only App Lab sketch and the 13×8 Matrix. Each product supplies a versioned grayscale animation manifest; a local request protocol plays named animations, a short status label, or a temporary pairing display. Requests from the unselected app are rejected, and stale requests expire. When no app is selected, the Matrix shows Router's neutral animation. Both product Linux services run continuously in separate Compose projects; their own sketches are not started or flashed during normal installation. Router grants one renewable controller input lease at a time and revokes it before granting another. At boot no lease is granted. The selected app's console input stops when the lease expires or Router stops.

The port-80 browser container talks only to a private Compose bridge and a user-owned Unix socket. The host helper accepts fixed app identifiers and cannot edit console controller assignments. Those remain in each product's Setup page. Existing pairing, game registries, and controller assignments remain in place during upgrades. The installer backs up software and restores the previous working version if startup fails.

R.O.B. Vision and VirtualGlove vendor the same `router_shared` package from this directory. Project-specific setup remains in their own adapters: R.O.B. Vision adds Buddy to Player 2; VirtualGlove chooses its gesture player and handles its pairing protocol.

Run `python3 scripts/sync.py --virtualglove /path/to/PowerGlove` here to update both projects. Add `--check` to detect drift. Do not edit a vendored copy directly. The package has no network or ROM dependencies; Linux uinput, udev and RetroArch are required for live routing.

## Host-project boundary

The library maintains the version 2 Player 1–4 assignment document and the
`VirtualGlove Merged Player N` device names used by existing installations.
A host project chooses when to install, pair, activate, and reconfigure it. It
may describe a fixed virtual gamepad in a small JSON file and set
`CONTROLLER_ROUTER_SOURCES_FILE` for the Router service:

```json
{
  "schema": 1,
  "sources": [{
    "name": "Example Maker Pad", "vendor": "1209", "product": "0002",
    "mapping": [{"name": "a", "type": "button", "code": 0,
                 "value": 1, "evdev_code": 304}]
  }]
}
```

The descriptor maps a known device identity to its fixed evdev controls. It
does not choose a player. The host adapter does that through `RouterStore`, as
R.O.B. Vision does for Buddy's Player 2 and VirtualGlove does for its gesture
player. Signed pairing protocols and web pages stay in the host projects.

## Development and validation

```sh
python3 -m unittest discover -s tests
python3 scripts/sync.py --virtualglove /path/to/PowerGlove
python3 scripts/sync.py --check --virtualglove /path/to/PowerGlove
```

The library is vendored so each console installer contains a complete offline
copy. Its `pyproject.toml` also permits packaging it independently for a future
controller project.
