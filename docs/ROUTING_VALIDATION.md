# Session routing validation

Test date: 28 September 2026. These results apply to the working implementation;
they do not describe an already published release.

## Environments

| Console | RetroArch | Routing mode | Evidence |
| --- | --- | --- | --- |
| retropieconsole, Raspberry Pi, ARM Linux | Installed 1.19.1 | Legacy udev | Actual RetroPad reads, keyboard Start, exit hotkey, source reconnects, five bounded core boots |
| Same console, separate upstream v1.20.0 build | 1.20.0 | Strict native reservations | Same input trace and reconnect tests; installed RetroArch was not replaced |
| Batocera 43.1, x86_64 | Installed 1.22.2 | Strict native reservations | Installed configgen command generation, five bounded core boots, repeat integration installation |
| Recalbox 10.1.1, `rpizero2` target, ARMv7 | Installed 1.22.2 | Strict native reservations | Paired to UNO Q; Gyromite, Stack-Up, and Super Glove Ball each launched through the installed generator adapter and exited cleanly in bounded tests on 29 September 2026 |

The Recalbox game checks stopped EmulationStation briefly so RetroArch could
take the display; the menu was restored after each check. The UNO Q reported
Gyromite and Stack-Up sessions and cleared each on exit. These checks establish
startup, routing selection, and session reporting. They do not establish a
complete human-played command sequence or Player 1 button response on Recalbox.
With the receiver in trace mode, the Gyromite FCEUmm wrapper also delivered a
frame packet to the receiver's Unix socket; the receiver identified its sender
PID and game. The trace began with neutral frame `N`. Normal receiver and menu
services were restored afterward.

During a bounded Super Glove Ball launch on the same Recalbox host, Router
selected VirtualGlove, marked its game active, and kept R.O.B. Vision
unselected. After exit, Router returned to no selection with the Matrix ready.

The separate 1.20.0 executable was built from upstream tag `v1.20.0`, with
udev enabled and graphics/audio backends omitted for the input trace. It is a
test executable, not a replacement console frontend.

## Automated checks

The shared launch suite covers exact name and vendor/product matching, actual
udev slot order, missing outputs, duplicate identities, native feature detection,
append order, retained command arguments, profile repair, repeat installation,
unknown Batocera generator layouts, and assignment reload without output deletion.
The shared library and both products' Router, packaging, and setup suites also
passed. Packaging negative tests intentionally report corrupt downloads or
incompatible cores; those messages are expected test cases.

Repeat integration installation leaves saved RetroArch files unchanged. Tests
preserve unrelated profiles, custom exit hotkeys, native hand-input arguments,
environment prefixes, and previous appended configurations. Each changed
integration file receives a recoverable backup.

## Live input trace

`tests/live/input_trace.c` is a minimal libretro test core. It records the button
masks actually returned to a core for Players 1 and 2; it contains no game data.
`tests/live/hotplug_trace.py` creates isolated physical-source fixtures and uses
the production Router engine and launch adapter.

Both RetroArch 1.19.1 and the separate 1.20.0 build passed:

1. Keyboard Enter reached Player 1 as Start.
2. Player 1 A and Player 2 B reached their respective core ports.
3. Both physical-source fixtures disconnected.
4. They reconnected in reverse order.
5. Player 1 B and Player 2 A still reached the saved players.
6. The merged output sysfs identities remained unchanged.
7. Player 1's hotkey plus Start exited the session. Two presses were used because
   RetroArch's test configuration retained its quit-confirmation behavior.

These are Linux uinput disconnect/reconnect tests. They model a sleeping or
waking wireless source; they are not a physical wireless-controller endurance
test. Real controllers should still be checked for Bluetooth, receiver, and
firmware-specific behavior.

## Native reservation startup correction

An initial 1.20.0 test crashed inside `reallocate_port_if_needed()` before the
first core frame. Giving Players 1 and 2 their discovered indexes while leaving
higher players at default indexes produced duplicate entries. The reservation
allocator's inverse map then contained uninitialized holes.

The adapter now supplies a complete permutation of all 16 initial indexes in its
temporary configuration, retaining each configured merged output's correct slot.
The unmodified upstream 1.20.0 executable then passed the live input trace.
This correction changes no saved RetroArch settings.

Upstream reference: [RetroArch v1.20.0 reservation allocator](https://github.com/libretro/RetroArch/blob/v1.20.0/tasks/task_autodetect.c).

## Service-loss test

During an active legacy trace, the merged outputs were deliberately removed and
the production Router service was started. The adapter logged the relaunch
instruction. Router refused to recreate the pads while the core was running.
The test then ended the session and restored the normal service. No recovery
claim was made for the interrupted game. A separate test killed the adapter with
SIGKILL and confirmed that its RetroArch child terminated instead of remaining
as a running orphan.

## Game boot checks

The following games completed bounded 180-frame boots on both consoles:

| Game | RetroPie command | Batocera core |
| --- | --- | --- |
| Gyromite | lr-robvision-fceumm | robvision_fceumm |
| Stack-Up | lr-robvision-nestopia | robvision_nestopia |
| Super Glove Ball | lr-nestopia-powerglove | nestopia_powerglove |
| Gyruss | lr-fceumm | fceumm |
| Bust A Move Deluxe, PSP | lr-ppsspp | ppsspp |

RetroPie tests execute the installed `emulators.cfg` commands. Batocera tests
call its installed Libretro generator, verify that the returned command contains
the adapter, then execute it. Null rendering/audio and a frame limit keep these
checks bounded. Batocera's generated settings were unchanged by each resulting
RetroArch process and its prior generated file was restored after the test.

The checks demonstrate command integration and core startup. They do not claim
full gameplay, a visible gate response, gesture tracking, PSP graphics accuracy,
or every possible game override. Game content stayed on the consoles and was not
included in test artifacts or packages.

## Saved configuration and recovery

The primary console's global, NES, and PSP `retroarch.cfg` checksums were
identical before and after live input tests, core boots, repeat integration
installation, and reboot. Ownership remained `pi:pi`; global and NES modes were
644 and PSP was 600. Existing assignments and pairing credentials were retained.

Batocera's first reboot exposed a concurrent-start race: the two products could
create duplicate Router outputs before either socket became ready. A shared
process-lifetime ownership lock now prevents that race. A second reboot produced
one Router process, unique Player 1/2 identities, and the restored generator
adapter. A duplicate-start attempt on RetroPie was rejected without replacing
its existing outputs.

The two Batocera product entry points were also started in both orders. In each
order, the first process owned the outputs and the second was rejected without
replacing the socket. The normal shared provider was restored afterward. This
tests process ownership; it is distinct from a fresh product-installation test.

## Remaining release checks

Before advertising broader verification, complete physical wireless sleep/wake
tests during visible gameplay, both product installation orders on fresh
systems, and a longer unattended run. Other RetroArch drivers, older versions,
and additional Batocera versions require their own validation. This change does
not require a RetroArch upgrade.

## Per-system selection validation

The shared scope tests verify selected system IDs, legacy NES/all behavior, two systems sharing one core, opt-out for NES, older-client assignment saves, revision-checked rollback, and blocking changes during an unmanaged game. Browser checks on both UNO Qs found no JavaScript errors or mobile horizontal overflow; NES opt-out switches to individual selection without saving automatically.

On retropieconsole.local (RetroArch 1.19.1), NES/Gyruss, Genesis/Sonic, and PSP/Bust A Move Deluxe each completed 120-frame enabled and disabled boots. Enabled runs contained Router diagnostics; disabled runs added no Router routing configuration. The exact original Router document and previous-save document were restored. All saved RetroArch hashes and ownership matched, and merged output sysfs identities stayed unchanged. These bounded checks verify launch integration, not extended physical gameplay.

Batocera 43.1 / RetroArch 1.22.2 also completed enabled and disabled 120-frame NES, Genesis, and PSP launches using its actual Libretro generator. The original Router settings and generated configuration were restored. The authenticated UNO Q browser save successfully disabled NES and browser rollback restored all-systems mode; the original files and previous-save history were then restored byte for byte.

On retropie.local (RetroArch 1.22.2), Gyromite completed enabled and disabled 120-frame NES launches through the installed adapter. Routing diagnostics appeared only in the enabled run. Personal settings and save history were restored, saved RetroArch configurations were unchanged, and merged output identities stayed unchanged. This console has no Genesis or PSP game library, so those systems were tested on the primary RetroPie console and Batocera instead.
