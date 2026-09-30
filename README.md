# Controller Router

Controller Router puts each gamepad with the player you choose. It combines configured physical and maker-controller inputs into stable Players 1–4 for RetroArch, while keeping EmulationStation button mappings. You can use it for NES alone, selected Libretro systems, or all supported Libretro systems. **My existing setup** leaves a system's normal controls in place.

VirtualGlove and R.O.B. Vision bundle this shared project for their Linux consoles and controller. Those installers install or upgrade Router; there is no separate player installation step. VirtualGlove's Windows LaunchBox path uses its own input integration. This checkout describes the current development version. A published product installer may contain an earlier Router version, so follow the guide included with that release.

## Get started

- [User Guide](docs/USER_GUIDE.md): choose players and systems, test a pad, and recover a game.
- [Pairing Guide](docs/PAIRING_GUIDE.md): connect a console once and check each app's access.
- [Integration Guide](docs/INTEGRATION_GUIDE.md): add an unusual controller or game.
- [Deployment Guide](docs/DEPLOYMENT_GUIDE.md): package and upgrade a Router integration.
- [Technical Reference](docs/TECHNICAL_REFERENCE.md): APIs, leases, Matrix display, storage, and failure behavior.

The controller's **Help** page offers shorter, task-based instructions and links to the printable PDFs in [output/pdf](output/pdf/). The [documentation library](docs/README.md) is the complete reading map.

## On the console

Router discovers physical controllers configured in EmulationStation and combines their inputs with assigned virtual sources. Saved player assignments and system choices survive upgrades. Fresh configurations use Router for NES only; existing choices remain when an installation is upgraded. A game must end before assignments change.

When a routed RetroArch game starts, Router resolves its merged gamepads by identity and supplies settings for that launch. Runtime routing does not rewrite saved `retroarch.cfg` files. It supports the legacy numeric-slot path and a native reservation path where the selected RetroArch build supports it. Wireless pads can sleep and reconnect without changing their merged player output; if Router itself loses that output during play, exit and relaunch the game after recovery.

VirtualGlove chooses its gesture player, and R.O.B. Vision places Buddy on Player 2. Game profiles, ROM filenames, emulator wrappers, and game actions remain in those products.

## On the controller

The optional portal is the entry page and Matrix display owner for the two current apps. It uses port 80; VirtualGlove's site uses 8100 and R.O.B. Vision's uses 8101. With one app installed, opening the controller address opens it. With both installed, **Apps** lets you choose. Both app services stay running. A registered game selects its app automatically, so a browser does not need to stay open for input. Manual switching waits until the game ends.

Router owns the shared 13×8 Matrix firmware. Product manifests define their animations, and a local request API displays the selected app's cues. When no app is selected, Router shows its neutral animation. One renewable input lease allows only the selected app to control a game; an absent, expired, or conflicting lease releases input.

Pairing is also shared. Choose **Pair console** from Apps to open Router's secure setup page on HTTPS port 8444. One confirmed console connection provisions separate private credentials for whichever supported apps are installed. Adding the other app later can provision it without pairing again. See the [Pairing Guide](docs/PAIRING_GUIDE.md) for the code, certificate, and Matrix confirmation steps.

## Extend Router

The dependency-free `router_shared` package exposes player assignment and input-routing APIs. A host project can supply a fixed virtual gamepad descriptor through `CONTROLLER_ROUTER_SOURCES_FILE`, then assign that source through `RouterStore`. For example:

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

The descriptor identifies controls; it does not create the device or select a player. A new project supplies its own receiver and game logic. The [Integration Guide](docs/INTEGRATION_GUIDE.md) explains that boundary and gives VirtualGlove and R.O.B. Vision examples. The current portal explicitly recognizes those two apps; a third app also needs portal registration and a display manifest.

## Develop and validate

Edit shared code here, then sync both product bundles:

```sh
python3 -m unittest discover -s tests
python3 scripts/sync.py --virtualglove /path/to/PowerGlove
python3 scripts/sync.py --virtualglove /path/to/PowerGlove --check
```

The library has no ROM or network dependency. Live console routing requires Linux uinput, udev, and RetroArch. See the [Deployment Guide](docs/DEPLOYMENT_GUIDE.md) for product packaging and the [Technical Reference](docs/TECHNICAL_REFERENCE.md) for its security and runtime contracts.
