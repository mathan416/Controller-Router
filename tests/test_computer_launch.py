import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from router_shared import computer_launch


class ComputerLaunchTests(unittest.TestCase):
    def test_launch_and_bridge_shutdown(self):
        with tempfile.TemporaryDirectory() as tmp:
            marker = Path(tmp) / 'stopped'
            code = "import sys,pathlib; print('READY',flush=True); sys.stdin.read(); pathlib.Path(sys.argv[1]).write_text('closed')"
            real_popen = computer_launch.subprocess.Popen
            calls = []
            def popen(args, **kwargs):
                calls.append(args)
                if len(calls) == 1:
                    args = [sys.executable, '-u', '-c', code, str(marker)]
                return real_popen(args, **kwargs)
            with patch.object(computer_launch.subprocess, 'Popen', side_effect=popen):
                code = computer_launch.launch('simcoupe', [sys.executable, '-c', 'raise SystemExit(7)'])
            self.assertEqual(code, 7)
            self.assertEqual(marker.read_text(), 'closed')

    def test_failed_bridge_does_not_start_emulator(self):
        real_popen = computer_launch.subprocess.Popen
        calls = []
        def popen(args, **kwargs):
            calls.append(args)
            return real_popen([sys.executable, '-c', 'pass'], **kwargs)
        with patch.object(computer_launch.subprocess, 'Popen', side_effect=popen):
            with self.assertRaises(RuntimeError):
                computer_launch.launch('simcoupe', ['must-not-run'])
        self.assertEqual(len(calls), 1)
