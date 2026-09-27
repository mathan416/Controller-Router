# Controller Router library

Shared, dependency-free Linux controller routing for maker projects. It discovers EmulationStation gamepads, persists stable Player 1–4 assignments, combines physical and virtual inputs into uinput gamepads, and maps those outputs into RetroArch.

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
