import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from router_shared import uno_halt as mod


class UnoHaltHelperTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        compatible = self.root / 'proc/device-tree/compatible'
        compatible.parent.mkdir(parents=True)
        compatible.write_bytes(b'arduino,imola\0qcom,qcm2290\0')

    def tearDown(self):
        self.temp.cleanup()

    def path(self, relative):
        return self.root / relative

    def test_installs_fixed_purpose_units_and_is_idempotent(self):
        self.assertEqual(mod.install(self.root), 'Halt helper files written.')
        unit = self.path('etc/systemd/system/controller-router-halt.service').read_text()
        self.assertIn('ConditionPathExists=/home/arduino/.local/state/controller-router/.halt-enabled', unit)
        self.assertIn('ExecStart=/usr/bin/systemctl --no-block halt', unit)
        self.assertNotIn('poweroff', unit)
        watcher = self.path('etc/systemd/system/controller-router-halt.path').read_text()
        self.assertIn('PathExists=/home/arduino/.local/state/controller-router/halt-request', watcher)
        tmpfiles = self.path('etc/tmpfiles.d/controller-router-halt.conf').read_text()
        self.assertIn('f /home/arduino/.local/state/controller-router/.halt-enabled 0644 arduino arduino', tmpfiles)
        for relative in mod.FILES:
            self.assertEqual(self.path(relative).stat().st_mode & 0o777, 0o644)
        before = {relative: self.path(relative).read_bytes() for relative in mod.FILES}
        mod.install(self.root)
        self.assertEqual({relative: self.path(relative).read_bytes() for relative in mod.FILES}, before)

    def test_refuses_pending_request_unrelated_file_symlink_and_other_boards(self):
        request = self.path(mod.REQUEST.lstrip('/'))
        request.parent.mkdir(parents=True)
        request.write_text('halt\n')
        with self.assertRaisesRegex(ValueError, 'pending'):
            mod.install(self.root)
        request.unlink()
        unrelated = self.path('etc/systemd/system/controller-router-halt.service')
        unrelated.parent.mkdir(parents=True)
        unrelated.write_text('[Service]\nExecStart=/bin/true\n')
        with self.assertRaisesRegex(ValueError, 'unrelated'):
            mod.install(self.root)
        unrelated.unlink()
        outside = self.root / 'outside.service'
        outside.write_text('x')
        unrelated.symlink_to(outside)
        with self.assertRaisesRegex(ValueError, 'symlink'):
            mod.install(self.root)
        unrelated.unlink()
        self.path('proc/device-tree/compatible').write_bytes(b'raspberrypi,4-model-b\0')
        with self.assertRaisesRegex(ValueError, 'UNO Q only'):
            mod.install(self.root)

    def test_live_install_needs_root_and_enables_watcher(self):
        with patch.object(mod.os, 'geteuid', return_value=1000):
            with self.assertRaisesRegex(ValueError, 'Root is required'):
                mod.install(Path('/'))
        calls = []
        def runner(command, **kwargs):
            self.assertTrue(kwargs.get('check'))
            calls.append(command)
        self.assertEqual(mod.install(self.root, runner=runner, apply=True),
                         'Installed the Controller Router halt helper.')
        self.assertEqual(calls, [['systemd-tmpfiles', '--create', '/etc/tmpfiles.d/controller-router-halt.conf'],
                                 ['systemctl', 'daemon-reload'],
                                 ['systemctl', 'enable', '--now', 'controller-router-halt.path']])
        calls.clear()
        self.assertEqual(mod.install(self.root, runner=runner, apply=True),
                         'Controller Router halt helper already installed.')
        self.assertNotIn(['systemctl', 'daemon-reload'], calls)  # unchanged files need no reload


if __name__ == '__main__':
    unittest.main()
