"""Stop only verified shared Router processes on an idle Batocera test device."""
import os
import fcntl
import signal
import time
from pathlib import Path

expected_config = '/userdata/system/virtualglove/data/controller-router.json'
expected_socket = '/run/virtualglove/merged-gamepad.sock'
targets = []
for entry in Path('/proc').iterdir():
    if not entry.name.isdigit():
        continue
    try:
        command = entry.joinpath('cmdline').read_bytes().decode().rstrip('\0').split('\0')
        if command and Path(command[0]).name == 'retroarch' and any(arg in command for arg in ('-L', '--libretro')):
            raise RuntimeError('End the running game before replacing Router outputs')
        if (len(command) > 4 and Path(command[0]).name == 'python3' and command[1] == '-m'
                and command[2] in ('virtualglove.controller_router', 'router_shared.controller_router')
                and command[3] == 'serve' and '--config' in command and '--socket' in command
                and command[command.index('--config')+1] == expected_config
                and command[command.index('--socket')+1] == expected_socket):
            fd = os.pidfd_open(int(entry.name))
            # Validate again after obtaining the stable process handle.
            if entry.joinpath('cmdline').read_bytes().decode().rstrip('\0').split('\0') != command:
                os.close(fd)
                continue
            targets.append((entry, fd))
    except (FileNotFoundError, ProcessLookupError):
        continue
try:
    for entry, fd in targets:
        signal.pidfd_send_signal(fd, signal.SIGTERM)
    deadline = time.monotonic() + 8
    while any(entry.exists() and not entry.joinpath('stat').read_text().split(') ', 1)[1].startswith('Z') for entry, _ in targets):
        assert time.monotonic() < deadline, 'Router did not stop; no outputs will be recreated'
        time.sleep(.1)
    # A process exit observation alone is not the ownership boundary.
    # Wait until the kernel releases its lock before creating new outputs.
    owner = Path('/run/virtualglove/controller-router-owner.lock')
    if owner.exists():
        lock_fd = os.open(str(owner), os.O_RDWR)
        try:
            while True:
                try:
                    fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except BlockingIOError:
                    assert time.monotonic() < deadline, 'Router ownership was not released'
                    time.sleep(.1)
        finally:
            os.close(lock_fd)
    print('Stopped %d verified shared Router processes' % len(targets))
finally:
    for entry, fd in targets:
        os.close(fd)
