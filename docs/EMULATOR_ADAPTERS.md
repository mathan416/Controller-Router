# Optional computer and emulator adapters

These source-level adapters are opt-in integration tools. They do not install an
emulator, change saved emulator settings, or certify a particular emulator build.
The installation owner must qualify the exact host and its original command using the native host contract in the
[Integration Guide](INTEGRATION_GUIDE.md#native-retropie-host-adapters).
Routing must be enabled for that system. When a registered native command
starts a bridge, its registry entry must also contain a separately qualified
`fallback_command` for the same emulator and media behavior. Router executes
that command when the system is set to **My existing setup**. It must not itself
start a Router bridge. Legacy entries without `fallback_command` retain their
existing pass-through command, which may still start a private bridge; do not
claim those installations have a working disabled-routing fallback until they
have been qualified. In the console command-line setup wizard, choose **Y (Systems)** to
select individual systems, NES only, or all supported systems; save to apply
the selection. On the UNO Q, use **Setup > Systems** for the same shared policy.
Changes take effect on the next launch. Never start the bridge alongside another bridge for the same game.

## Computer gamepad bridge

Install the `router_shared` package for the launching Python interpreter, or
include the installed Router library directory in `PYTHONPATH`.

Register the following command as the original command of a qualified
`native-route` entry for its system. The native route identifies the active game
to Router and applies the saved per-system policy; running this command directly
does not establish that session and is suitable only for diagnostics.

`python3 -m router_shared.computer_launch PROFILE -- EMULATOR [ARG ...]`
starts the bridge, waits for `READY`, then runs the supplied executable without
a shell. It stops the emulator on a SimCoupe exit chord or bridge failure, and
stops the bridge when the game exits. Its input is the already assigned Router
merged Player 1; `--player N` before PROFILE selects another Router player.
The emulator-facing name remains the profile's Player 1 name. The bridge needs
permission to read the merged event device and create a uinput device. Configure
OS device permissions for the launching account; do not run an entire emulator
as root simply to obtain those permissions.

| Profile | Device presented | Emulator requirement |
| --- | --- | --- |
| `arcem` | `ArcEm Routed Player 1` | A compatible ArcEm build that selects that device and maps its controls; stock ArcEm has not been qualified. |
| `gsplus` | `GSplus Routed Player 1` | A compatible GSplus build honoring `GSPLUS_ROUTER_NAME`; the launcher sets it. Stock builds have not been qualified. |
| `simcoupe` | `SAM Routed Player 1` | Configure SimCoupe to select that named device. |

For example, the original command in a qualified native SimCoupe entry could use your installed binary and your own media:

```sh
python3 -m router_shared.computer_launch simcoupe -- /path/to/simcoupe -joydev1 'SAM Routed Player 1' /path/to/game.dsk
```

For SimCoupe, pressing and releasing Hotkey alone toggles typing mode; in typing
mode the bridge neutralizes the gamepad so the physical keyboard remains usable.
Hotkey+Start or Select+Start ends the emulator. The original cabinet used a
separate per-game writable media copy: supply your own media management when
needed. This tool does not make or manage disk copies.

The `emulator-patches` directory includes input-only patches for ArcEm revision
`b682d4b5c9e1bd01138d46859adc1738e7eaf94a` and GSplus revision
`41e71031debbde98e66ea5c5c67498e9b4726a6d`. Each patch retains the
upstream project's GPL license, included next to it. Obtain the corresponding
source separately. On a Linux build host with the emulator's documented build
dependencies (SDL2 for ArcEm; CMake and SDL3 for GSplus), run:

```sh
python3 emulator-patches/build.py arcem /path/to/arcem-source /new/path/arcem-build
python3 emulator-patches/build.py gsplus /path/to/gsplus-source /new/path/gsplus-build
```

The builder validates the upstream input source hash, copies it to a new build
directory, applies the patch and builds there; it never installs an executable.
GSplus's upstream CMake may fetch its pinned SDL3 release if no local SDL3
package is available. Pass CMake options individually with `--cmake-arg=...`;
for a console-only build, the host may need `--cmake-arg=-DSDL_X11=OFF` and
`--cmake-arg=-DSDL_WAYLAND=OFF` together with its SDL KMSDRM and audio options.
The wheel includes the builder and patches under `share/controller-router/emulator-patches`. Supply ROMs, media, and system-specific emulator settings
separately. Test the resulting build and retain your previous executable.
Confirm the build accepts the named device, its button mapping and exit behavior
before registering it. The
bridge reads the merged output instead of re-reading physical assignments, so
Router's source assignments and disconnect release behavior remain in effect.

## Safe exit for native computer fallbacks

The RetroPie installer provides `native-exit-run` and `native-exit-watch`.
A qualified host fallback may run an emulator through `native-exit-run --
/absolute/path/to/emulator ...` to retain the cabinet's physical Hotkey+Start
or Select+Start exit. The watcher reads the already assigned Player 1 physical
sources without grabbing them, forwarding gameplay input, changing emulator
settings, or creating a virtual joystick. Both buttons must come from the same
source. Axis-only mappings are ignored; a missing Player 1 assignment fails
before the emulator starts. Assigned sleeping devices can reconnect. The
supervisor terminates only its own emulator and cleans up the watcher on exit.

This exit control is independent of the emulator's own keyboard and joystick
settings. If all assigned devices are disconnected, a physical exit is not
available until one reconnects. Test the actual controller and native game
before relying on the chord.

## DICE and Flycast host provider

`router_shared/emulator_hosts.py` is an optional provider for the existing
administrator-owned native-adapters manifest. On RetroPie the installer automatically
registers existing ArcEm, GSplus and SimCoupe private bridges when their exact
launcher, native registry entry, emulator name, and original executable all match.
It retains other native registrations and does not change launchers or defaults.
For other qualified host commands, it also registers them when
`/etc/controller-router/emulator-qualification.json` exists. The qualification must contain schema 1 and a `systems` list; each entry
contains an absolute `config` path, `system`, `kind` (`native` or
`custom-libretro`), and `command_sha256` (a list of hashes of exact commands in
that config). Generate each hash from the exact unquoted command, without the
newline, after verifying the launcher. The installer refuses stale hashes and
merges the provider and entries into the existing manifest. With no qualification
file, it leaves the host registration alone. This does not create or modify the
emulator launcher. Configure the provider separately in
`/etc/controller-router/emulator-hosts.json`. This
configuration is executable-adjacent administrator configuration: keep it
root-owned and not writable by game users.

Example configuration (replace every path with the verified paths on the host):

```json
{
  "schema": 1,
  "flycast_dreamcast_controls": true,
  "loader_sessions": [{
    "loader": "/absolute/path/to/ld-linux",
    "frontend": "/absolute/path/to/retroarch",
    "core_argument": "/mounted/path/to/dice_libretro.so",
    "config_argument": "/absolute/path/to/dice/retroarch.cfg",
    "installed_core": "/absolute/path/to/installed/dice_libretro.so",
    "system": "dice",
    "core_name": "dice_libretro.so"
  }]
}
```

The loader detector verifies the configured command arguments, the running loader
identity and mounted core identity. An incorrect or missing configuration does
not match. It does not install DICE or create its isolated runtime. Flycast's
optional Dreamcast transform maps L1/R1 to the corresponding L2/R2 triggers and
uses the D-pad for a neutral analog stick. Leave it disabled where the emulator
already supplies a different mapping. It does not configure Flycast's own
peripheral or input settings.

Test each qualified installation in an actual game: player assignment, buttons,
analog and D-pad, keyboard mode, exit, disconnect/reconnect, cleanup, disabled
routing, and the original fallback. Automated tests do not establish physical
hardware or emulator compatibility.

## Qualify a fresh RetroPie host

The setup utility wraps one existing emulator choice, retaining its exact current
command as the disabled-routing fallback. It does not create emulator media,
BIOS, or emulator-specific per-title launch scripts. First install a compatible
emulator and test the existing choice independently with Router disabled,
including its controls, exit path and writable media. Copy its **exact command**
from the relevant `emulators.cfg`, excluding the surrounding quotation marks,
and calculate its SHA-256 without a newline:

```sh
printf %s 'THE EXACT TESTED ORIGINAL COMMAND' | sha256sum
```

Stop EmulationStation and any game before installation. Install the Router
package and native route on RetroPie, then run the setup with the account and
state directory used by the installed native registry. This example is a dry run;
replace every path and hash with values from the host:

```sh
sudo env PYTHONPATH=/opt/controller-router/lib /usr/bin/python3 -m router_shared.emulator_setup \
  simcoupe --choice simcoupe --runtime-user pi \
  --state-root /home/pi/.local/share/controller-router/native \
  --routed-command '/opt/controller-router/bin/computer-launch simcoupe -- /path/to/simcoupe -joydev1 "SAM Routed Player 1" %ROM%' \
  --fallback-sha256 TESTED_COMMAND_SHA256 --fallback-tested
```

To use a different merged player, place `--player N` before the profile in
`--routed-command`, for example `computer-launch --player 2 simcoupe -- ...`.

`--fallback-tested` is an explicit attestation that the original command was
actually tested independently; a matching hash alone cannot establish that.
Review the plan, then repeat with `--apply`. It creates the shared
`computer-launch` executable if absent, adds a native registry entry and a
catalogue registration, and wraps only the chosen emulator line. The original
command is retained verbatim as `fallback_command` and its hash is recorded;
other entries and the default choice are preserved. A conflicting registration,
changed source file, missing executable or active game stops the operation.
Backups are kept under `/var/backups/controller-router`. Run setup again to
verify idempotence. Configuration writes are checked for concurrent changes. The CLI takes an
advisory setup lock, but other tools do not necessarily share it; keep
EmulationStation and other configuration writers stopped throughout the operation.
Untracked native launchers cannot all be detected reliably.

On an existing host, pass its actual registry launcher, runtime user and state
root rather than replacing its registry. Commands requiring `CON:` or `XINIT:`
prefixes, shell operators or expansions, quoted or embedded launch placeholders,
an already routed original, or an emulator-specific writable-disk wrapper need
their own separately qualified host adapter; this utility refuses to guess a
fallback. Setup requires the installer-owned `native-route` stub that imports the
same installed Router library as the adjacent provider; custom or stale native
launchers that differ from that exact stub are refused. Use a separately
qualified host-specific integration for them. The default wheel does not install system services; use the
product installer before this procedure. Run setup with the same installed
Router library used by the configured native launcher: the fallback capability
check applies to that library and cannot qualify an unrelated or stale launcher
copy. Verify enabled and disabled launches in actual games before advertising
support. The setup catalogue follows the default emulator choice; if the wrapped
choice is not the default, it does not change that default automatically.
