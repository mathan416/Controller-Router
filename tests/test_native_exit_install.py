import tempfile
import unittest
from pathlib import Path
from router_shared.launch_install import install_retropie

class NativeExitInstallTests(unittest.TestCase):
    def test_installs_idempotent_passive_watcher_and_runner(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)/'router';configs=Path(temp)/'configs';configs.mkdir()
            install_retropie(configs,root)
            watcher=root/'bin/native-exit-watch'; runner=root/'bin/native-exit-run'
            self.assertTrue(watcher.is_file());self.assertTrue(runner.is_file())
            self.assertEqual(watcher.stat().st_mode & 0o777,0o755)
            self.assertEqual(runner.stat().st_mode & 0o777,0o755)
            self.assertIn('router_shared.passive_exit_watcher',watcher.read_text())
            self.assertIn('router_shared.native_exit_launch',runner.read_text())
            self.assertIn(str(watcher),runner.read_text())
            self.assertTrue((root/'lib/router_shared/passive_exit_watcher.py').is_file())
            self.assertTrue((root/'lib/router_shared/native_exit_launch.py').is_file())
            self.assertEqual(install_retropie(configs,root),[])
