"""Verify concurrent product Router startup in both orders, on an idle console."""
import json
import os
import subprocess
import time
from pathlib import Path

config = '/userdata/system/virtualglove/data/controller-router.json'
socket = '/run/virtualglove/merged-gamepad.sock'
stop_script = Path(__file__).with_name('stop_batocera_routers.py')
subprocess.run(['python3', str(stop_script)], check=True)
process = None
results = []

def start(root, module, log):
    env = dict(os.environ)
    env['PYTHONPATH'] = root + ('/src' if root.endswith('virtualglove') else '')
    return subprocess.Popen(['python3', '-m', module, 'serve', '--platform', 'batocera',
                             '--config', config, '--socket', socket], cwd=root,
                            env=env, stdout=log, stderr=log)

providers = [('/userdata/system/rob-vision', 'router_shared.controller_router'),
             ('/userdata/system/virtualglove', 'virtualglove.controller_router')]
try:
    for first, second in (providers, providers[::-1]):
        with open('/userdata/system/controller-router-session-test/owner.log', 'a') as log:
            process = start(*first, log)
            deadline = time.monotonic() + 15
            while not Path(socket).exists() or Path('/run/virtualglove/controller-router-owner.lock').read_text() != str(process.pid):
                assert process.poll() is None and time.monotonic() < deadline, (
                    'Router did not become ready', first, process.pid, process.poll(),
                    Path('/run/virtualglove/controller-router-owner.lock').read_text(), Path(socket).exists())
                time.sleep(.1)
            # The adapter independently rejects any duplicate device identity.
            output = subprocess.check_output(['/userdata/system/controller-router/bin/retroarch-route',
                                              '/usr/bin/retroarch', '--version'], stderr=subprocess.STDOUT, text=True)
            assert 'native-reservations' in output
            loser = start(*second, log)
            assert loser.wait(timeout=5) == 1
            assert process.poll() is None and Path(socket).exists()
            results.append({'first': first[1], 'second': second[1], 'duplicate_rejected': True})
            process.terminate(); process.wait(timeout=5); process = None
    print(json.dumps(results))
finally:
    if process and process.poll() is None:
        process.terminate(); process.wait(timeout=5)
    # Restore the normal shared provider and its service PID record.
    with open('/userdata/system/virtualglove/log/controller_router.log', 'a') as log:
        process = start('/userdata/system/virtualglove', 'router_shared.controller_router', log)
    Path('/userdata/system/virtualglove/run/controller_router.pid').write_text(str(process.pid))
    time.sleep(2)
    assert process.poll() is None, 'Normal Router provider did not restart'
