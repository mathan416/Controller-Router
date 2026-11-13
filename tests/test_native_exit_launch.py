import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

HERE=Path(__file__).resolve().parent
from router_shared import native_exit_launch as launcher


class SupervisorTests(unittest.TestCase):
    def test_chord_terminates_only_emulator_and_closes_watcher(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);watcher=root/'watcher.py';marker=root/'watcher-closed'
            watcher.write_text('import sys,time,pathlib\nprint("READY",flush=True)\ntime.sleep(.2)\nprint("EXIT",flush=True)\nsys.stdin.read()\npathlib.Path(sys.argv[1]).write_text("closed")\n')
            # The fixture accepts watcher arguments; use its --config value as marker.
            code=watcher.read_text().replace('sys.argv[1]', 'sys.argv[2]');watcher.write_text(code)
            result=launcher.launch(watcher,marker,root/'es.xml',[sys.executable,'-c','import time; time.sleep(30)'])
            self.assertEqual(result,0);self.assertEqual(marker.read_text(),'closed')

    def test_watcher_failure_does_not_start_emulator(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);watcher=root/'bad.py';watcher.write_text('raise SystemExit(1)\n')
            marker=root/'emulator-started'
            with self.assertRaisesRegex(RuntimeError,'did not become ready'):
                launcher.launch(watcher,root/'config',root/'es.xml',
                    [sys.executable,'-c','from pathlib import Path; Path(%r).touch()'%str(marker)])
            self.assertFalse(marker.exists())

    def test_watcher_loss_stops_running_emulator(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);watcher=root/'watcher.py';stopped=root/'stopped'
            watcher.write_text('import time\nprint("READY",flush=True)\ntime.sleep(.5)\n')
            child=('import pathlib,signal,time,sys; '
                   'signal.signal(signal.SIGTERM,lambda *_:(pathlib.Path(%r).touch(),sys.exit(0))); '
                   'time.sleep(30)' % str(stopped))
            with self.assertRaisesRegex(RuntimeError,'stopped unexpectedly'):
                launcher.launch(watcher,root/'config',root/'es.xml',[sys.executable,'-c',child])
            self.assertTrue(stopped.exists())

    def test_normal_emulator_exit_preserves_code_and_closes_watcher(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);watcher=root/'watcher.py';marker=root/'closed'
            watcher.write_text('import sys,pathlib\nprint("READY",flush=True)\nsys.stdin.read()\npathlib.Path(sys.argv[2]).touch()\n')
            self.assertEqual(launcher.launch(watcher,marker,root/'es.xml',[sys.executable,'-c','raise SystemExit(7)']),7)
            self.assertTrue(marker.exists())

class ParentDeathTests(unittest.TestCase):
    @unittest.skipUnless(sys.platform.startswith('linux'), 'Linux prctl fixture')
    def test_supervisor_sigkill_stops_emulator_and_closes_watcher(self):
        import signal
        import time
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);watcher=root/'watcher.py';closed=root/'closed';started=root/'started';stopped=root/'stopped'
            watcher.write_text('import sys,pathlib\nprint("READY",flush=True)\nsys.stdin.read()\npathlib.Path(sys.argv[2]).touch()\n')
            child=('import pathlib,signal,time,sys; '
                   'signal.signal(signal.SIGTERM,lambda *_:(pathlib.Path(%r).touch(),sys.exit(0))); '
                   'pathlib.Path(%r).touch(); time.sleep(30)' % (str(stopped),str(started)))
            proc=subprocess.Popen([sys.executable,launcher.__file__,
                '--watcher',str(watcher),'--config',str(closed),'--es-inputs',str(root/'es.xml'),
                '--',sys.executable,'-c',child],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
            try:
                deadline=time.monotonic()+5
                while not started.exists() and time.monotonic()<deadline:time.sleep(.02)
                self.assertTrue(started.exists(),'emulator did not start')
                proc.kill();proc.wait(timeout=4)
                deadline=time.monotonic()+5
                while (not stopped.exists() or not closed.exists()) and time.monotonic()<deadline:time.sleep(.02)
                self.assertTrue(stopped.exists(),'emulator did not receive parent-death SIGTERM')
                self.assertTrue(closed.exists(),'watcher did not exit on parent EOF')
            finally:
                if proc.poll() is None:proc.kill();proc.wait()
                proc.stdout.close();proc.stderr.close()

class SignalCleanupTests(unittest.TestCase):
    def test_supervisor_termination_stops_emulator_and_watcher(self):
        import time
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);watcher=root/'watcher.py';closed=root/'closed';started=root/'started';stopped=root/'stopped'
            watcher.write_text('import sys,pathlib\nprint("READY",flush=True)\nsys.stdin.read()\npathlib.Path(sys.argv[2]).touch()\n')
            child=('import pathlib,signal,time,sys; '
                   'signal.signal(signal.SIGTERM,lambda *_:(pathlib.Path(%r).touch(),sys.exit(0))); '
                   'pathlib.Path(%r).touch(); time.sleep(30)' % (str(stopped),str(started)))
            proc=subprocess.Popen([sys.executable,launcher.__file__,
                '--watcher',str(watcher),'--config',str(closed),'--es-inputs',str(root/'es.xml'),
                '--',sys.executable,'-c',child],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
            try:
                deadline=time.monotonic()+5
                while not started.exists() and time.monotonic()<deadline:time.sleep(.02)
                self.assertTrue(started.exists(),'emulator did not start')
                proc.terminate();self.assertEqual(proc.wait(timeout=5),143)
                self.assertTrue(stopped.exists(),'emulator did not receive SIGTERM')
                self.assertTrue(closed.exists(),'watcher did not exit on parent EOF')
            finally:
                if proc.poll() is None:proc.kill();proc.wait()
                proc.stdout.close();proc.stderr.close()

class ParentDeathRaceTests(unittest.TestCase):
    @unittest.skipUnless(sys.platform.startswith('linux'), 'Linux prctl fixture')
    def test_parent_already_gone_resets_inherited_handler_and_terminates(self):
        import signal
        code=('import importlib.util,signal; '
              'spec=importlib.util.spec_from_file_location("runner",%r); '
              'm=importlib.util.module_from_spec(spec);spec.loader.exec_module(m); '
              'signal.signal(signal.SIGTERM,lambda *_: None); '
              'm.linux_parent_death(0); print("unexpected survival",flush=True)' % launcher.__file__)
        result=subprocess.run([sys.executable,'-c',code],capture_output=True,timeout=5)
        self.assertEqual(result.returncode,-signal.SIGTERM)
        self.assertNotIn(b'unexpected survival',result.stdout)
