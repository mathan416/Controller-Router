import tempfile
import unittest
from pathlib import Path
from router_shared.loader_session import loader_session


class LoaderSessionTests(unittest.TestCase):
    def test_exact_arguments_and_file_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            core = base / 'installed.so'; core.write_bytes(b'core')
            loader = base / 'loader'; loader.write_bytes(b'loader')
            process = base / 'proc/123'
            (process / 'root/session').mkdir(parents=True)
            (process / 'root/lib').mkdir()
            (process / 'root/session/core.so').symlink_to(core)
            (process / 'root/lib/loader').symlink_to(loader)
            (process / 'exe').symlink_to(loader)
            args = ['/lib/loader', '/opt/frontend', '-L', '/session/core.so', '--config', '/opt/dice.cfg']
            kwargs = dict(loader='/lib/loader', frontend='/opt/frontend', core_argument='/session/core.so',
                          config_argument='/opt/dice.cfg', installed_core=core, system='dice', core_name='dice_libretro.so')
            def run(argv):
                (process / 'cmdline').write_bytes(b'\0'.join(a.encode() for a in argv) + b'\0')
                return loader_session(base / 'proc', **kwargs)
            self.assertEqual(run(args), ('dice_libretro.so', 'dice'))
            for index in (0, 1, 3, 5):
                wrong = args.copy(); wrong[index] = '/other'
                self.assertEqual(run(wrong), (None, None))
            self.assertEqual(run(args + ['-L', '/other']), (None, None))
            self.assertEqual(run(args[:-1]), (None, None))
            (process / 'root/session/core.so').unlink()
            (process / 'root/session/core.so').write_bytes(b'other')
            self.assertEqual(run(args), (None, None))

    def test_relative_paths_rejected(self):
        with self.assertRaises(ValueError):
            loader_session('/proc', loader='loader', frontend='/frontend', core_argument='/core',
                           config_argument='/config', installed_core='/core', system='dice', core_name='dice')
