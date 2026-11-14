import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest

from router_shared import uno_boot_order as mod


class UnitOrderTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        p = self.root / 'proc/device-tree/compatible'
        p.parent.mkdir(parents=True)
        p.write_bytes(b'arduino,imola\0qualcomm,model\0')
        (self.root / 'etc/systemd/system').mkdir(parents=True)
        self.commands = []
        self.fields = 'LoadState=loaded\nUnitFileState=enabled\nType=oneshot\n'
        self.fail_reload = False
        self.app_fields = 'LoadState=loaded\n'
        self.after_fields = mod.UNIT + ' network-online.target\n'
        self.reload_restores_after = False

    def run_command(self, cmd, **kwargs):
        self.commands.append(cmd)
        if cmd[1] == 'show':
            text = self.after_fields if '--value' in cmd else (self.app_fields if cmd[2] == 'arduino-app-cli.service' else self.fields)
            return subprocess.CompletedProcess(cmd, 0, stdout=text)
        if self.fail_reload:
            raise subprocess.CalledProcessError(1, cmd)
        if self.reload_restores_after:
            self.after_fields = mod.UNIT + ' network-online.target\n'
        return subprocess.CompletedProcess(cmd, 0, stdout='')

    def target(self):
        return self.root / 'etc/systemd/system/arduino-app-cli.service.d' / mod.DROPIN

    def test_installs_ordering_only_and_is_idempotent(self):
        self.assertIn('Installed', mod.install(self.root, self.run_command))
        self.assertEqual(self.target().read_bytes(), mod.CONTENT)
        self.assertEqual(self.target().stat().st_mode & 0o777, 0o644)
        self.assertIn(b'After=arduino-burn-bootloader-unoq.service', mod.CONTENT)
        self.assertNotIn(b'Wants=', mod.CONTENT)
        self.assertNotIn(b'Requires=', mod.CONTENT)
        self.assertEqual(self.commands[2], ['systemctl', 'daemon-reload'])
        self.assertIn('already', mod.install(self.root, self.run_command))
        self.assertEqual(sum('daemon-reload' in c for c in self.commands), 1)
        self.assertFalse(any('restart' in c or 'start' in c for c in self.commands))

    def test_missing_writer_is_untouched(self):
        self.fields = 'LoadState=not-found\nUnitFileState=\nType=\n'
        self.assertIn('not present', mod.install(self.root, self.run_command))
        self.assertFalse(self.target().exists())
        self.assertFalse(any('daemon-reload' in c for c in self.commands))

    def test_new_dropin_ineffective_is_removed_after_reload(self):
        self.after_fields = 'network-online.target\n'
        with self.assertRaisesRegex(RuntimeError, 'not effective'): mod.install(self.root, self.run_command)
        self.assertFalse(self.target().exists())
        self.assertEqual(sum('daemon-reload' in c for c in self.commands), 2)

    def test_existing_dropin_with_stale_manager_is_reloaded(self):
        self.target().parent.mkdir()
        self.target().write_bytes(mod.CONTENT)
        self.after_fields = 'network-online.target\n'
        self.reload_restores_after = True
        self.assertIn('effective', mod.install(self.root, self.run_command))
        self.assertEqual(self.target().read_bytes(), mod.CONTENT)
        self.assertEqual(sum('daemon-reload' in c for c in self.commands), 1)

    def test_existing_dropin_ineffective_is_retained(self):
        self.target().parent.mkdir()
        self.target().write_bytes(mod.CONTENT)
        self.after_fields = 'network-online.target\n'
        with self.assertRaisesRegex(RuntimeError, 'not effective'): mod.install(self.root, self.run_command)
        self.assertEqual(self.target().read_bytes(), mod.CONTENT)
        self.assertEqual(sum('daemon-reload' in c for c in self.commands), 1)

    def test_disabled_writer_remains_disabled_but_order_is_installed(self):
        self.fields = 'LoadState=loaded\nUnitFileState=disabled\nType=oneshot\n'
        self.assertIn('Installed', mod.install(self.root, self.run_command))
        self.assertEqual(self.target().read_bytes(), mod.CONTENT)
        self.assertFalse(any('enable' in c or 'start' in c for c in self.commands))
        self.assertNotIn(b'Wants=', mod.CONTENT)

    def test_wrong_board_and_unexpected_type_are_rejected(self):
        (self.root / 'proc/device-tree/compatible').write_bytes(b'not-uno\0')
        with self.assertRaises(ValueError): mod.install(self.root, self.run_command)
        (self.root / 'proc/device-tree/compatible').write_bytes(b'arduino,imola\0')
        self.fields = 'LoadState=loaded\nUnitFileState=enabled\nType=simple\n'
        with self.assertRaises(ValueError): mod.install(self.root, self.run_command)
        self.assertFalse(self.target().exists())

    def test_missing_app_lab_is_untouched(self):
        self.app_fields = 'LoadState=not-found\n'
        self.assertIn('not loaded', mod.install(self.root, self.run_command))
        self.assertFalse(self.target().exists())
        self.assertEqual(len(self.commands), 1)

    def test_symlink_ancestor_refused(self):
        base = self.root / 'etc/systemd/system'
        base.rmdir()
        parent = base.parent
        parent.rmdir()
        other = self.root / 'other'; other.mkdir()
        parent.symlink_to(other, target_is_directory=True)
        with self.assertRaises(ValueError): mod.install(self.root, self.run_command)
        self.assertFalse((other / 'system' / 'arduino-app-cli.service.d' / mod.DROPIN).exists())

    def test_existing_custom_dropin_not_overwritten(self):
        self.target().parent.mkdir()
        self.target().write_text('[Unit]\nAfter=other.service\n')
        with self.assertRaises(ValueError): mod.install(self.root, self.run_command)
        self.assertEqual(self.target().read_text(), '[Unit]\nAfter=other.service\n')

    def test_symlink_refused(self):
        other = self.root / 'other'; other.mkdir()
        self.target().parent.symlink_to(other, target_is_directory=True)
        with self.assertRaises(ValueError): mod.install(self.root, self.run_command)
        self.assertFalse((other / mod.DROPIN).exists())

    def test_failed_reload_removes_only_new_file(self):
        self.fail_reload = True
        with self.assertRaises(subprocess.CalledProcessError): mod.install(self.root, self.run_command)
        self.assertFalse(self.target().exists())
        self.assertEqual(sum('daemon-reload' in c for c in self.commands), 2)


if __name__ == '__main__':
    unittest.main()
