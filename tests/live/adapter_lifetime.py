"""Verify frontend SIGKILL of the adapter cannot orphan its RetroArch child."""
import os
import signal
import subprocess
import time
from pathlib import Path

root = Path('/home/pi/controller-router-session-test')
log_path = root / 'adapter-lifetime.log'
command = ['dbus-run-session', '--', '/opt/controller-router/bin/retroarch-route',
           '/opt/retropie/emulators/retroarch/bin/retroarch',
           '-L', str(root / 'router_input_trace_libretro.so'),
           '--config', str(root / 'live/trace.cfg'), '--verbose']

def children(pid):
    try:
        return [int(value) for value in Path('/proc/%d/task/%d/children' % (pid, pid)).read_text().split()]
    except FileNotFoundError:
        return []

with log_path.open('w') as log:
    process = subprocess.Popen(command, stdout=log, stderr=log, start_new_session=True)
    try:
        deadline = time.monotonic() + 15
        adapter = None
        while time.monotonic() < deadline:
            for pid in children(process.pid):
                try:
                    if b'retroarch-route' in Path('/proc/%d/cmdline' % pid).read_bytes():
                        adapter = pid
                except FileNotFoundError:
                    pass
            if adapter and 'ROUTER_TRACE frame=0' in log_path.read_text():
                break
            if process.poll() is not None:
                raise RuntimeError('Test session exited before becoming ready')
            time.sleep(.1)
        assert adapter and children(adapter), 'RetroArch did not become ready'
        core_pid = children(adapter)[0]
        os.kill(adapter, signal.SIGKILL)
        deadline = time.monotonic() + 5
        while Path('/proc/%d/stat' % core_pid).exists():
            if Path('/proc/%d/stat' % core_pid).read_text().split(') ', 1)[1].startswith('Z'):
                break
            assert time.monotonic() < deadline, 'RetroArch was orphaned'
            time.sleep(.1)
        process.wait(timeout=5)
        print('Frontend SIGKILL: RetroArch child terminated; no running orphan')
    finally:
        if process.poll() is None:
            os.killpg(process.pid, signal.SIGTERM)
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait(timeout=3)
