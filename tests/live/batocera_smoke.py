"""Bounded tests using Batocera's installed generator and console-local games."""
import hashlib
import json
import os
import signal
import subprocess
import tempfile
from pathlib import Path
from types import SimpleNamespace

from configgen.Emulator import Emulator
from configgen.generators.libretro.libretroGenerator import LibretroGenerator

root = Path('/userdata/system/controller-router-session-test')
root.mkdir(parents=True, exist_ok=True)
generated = Path('/userdata/system/configs/retroarch/retroarchcustom.cfg')
previous = generated.read_bytes() if generated.exists() else None
cases = [('gyromite', 'nes', 'robvision_fceumm', 'Gyromite (World).7z'),
         ('stackup', 'nes', 'robvision_nestopia', 'Stack-Up (World).7z'),
         ('super-glove-ball', 'nes', 'nestopia_powerglove', 'Super Glove Ball (USA).7z'),
         ('ordinary-nes', 'nes', 'fceumm', 'Gyruss (USA).7z'),
         ('psp', 'psp', 'ppsspp', 'Bust_A_Move_Deluxe_PSP.cso')]
results = []
try:
    for name, system_name, core, filename in cases:
        rom = Path('/userdata/roms') / system_name / filename
        args = SimpleNamespace(system=system_name, gameinfoxml='/dev/null', emulator='libretro',
                               core=core, lightgun=False, wheel=False, netplaymode=None,
                               netplaypass=None, netplayip=None, netplayport=None,
                               netplaysession=None, state_slot=None, autosave=None,
                               state_filename=None)
        system = Emulator(args, rom)
        system.config['video_driver'] = 'gl'
        with tempfile.TemporaryDirectory(prefix='routing-boot-', dir=str(root)) as folder:
            if system_name == 'nes':
                content = Path(folder) / (rom.stem + '.nes')
                content.write_bytes(subprocess.check_output(['7zr', 'x', '-so', str(rom)], stderr=subprocess.DEVNULL))
                assert content.read_bytes()[:4] == b'NES\x1a'
            else:
                content = rom
            command = LibretroGenerator().generate(system, content, [], {}, [], {},
                                                   {'width': 1280, 'height': 720})
            assert str(command.array[0]) == '/userdata/system/controller-router/bin/retroarch-route'
            # Generation is real; only rendering and duration change for this test.
            settings = Path(folder) / 'bounded.cfg'
            settings.write_text('video_driver = "null"\naudio_driver = "null"\n'
                                'gamemode_enable = "false"\nconfig_save_on_exit = "false"\n'
                                'pause_nonactive = "false"\nsavestate_auto_load = "false"\n'
                                'savestate_auto_save = "false"\n')
            before = hashlib.sha256(generated.read_bytes()).hexdigest()
            argv = list(map(str, command.array)) + ['--appendconfig', str(settings), '--max-frames', '180']
            env = dict(os.environ); env.update({k: str(v) for k, v in command.env.items()})
            log = root / (name + '-smoke.log')
            with log.open('w') as stream:
                process = subprocess.Popen(['dbus-run-session', '--'] + argv, env=env,
                                           stdout=stream, stderr=stream, start_new_session=True)
                try:
                    process.wait(timeout=40)
                finally:
                    if process.poll() is None:
                        os.killpg(process.pid, signal.SIGTERM)
                        try:
                            process.wait(timeout=3)
                        except subprocess.TimeoutExpired:
                            os.killpg(process.pid, signal.SIGKILL)
                            process.wait(timeout=3)
            text = log.read_text()
            assert process.returncode == 0, (name, process.returncode, str(log))
            assert '"mode": "native-reservations"' in text, (name, 'missing routing diagnostics')
            assert '[Core]' in text, (name, 'missing core boot')
            assert hashlib.sha256(generated.read_bytes()).hexdigest() == before
            results.append({'game': name, 'core': core, 'generated_adapter': True,
                            'exit': process.returncode, 'generated_settings_changed_by_runtime': False})
    print(json.dumps(results, indent=2))
finally:
    if previous is not None:
        generated.write_bytes(previous)
    elif generated.exists():
        generated.unlink()
