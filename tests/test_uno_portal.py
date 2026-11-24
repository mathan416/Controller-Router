import tempfile
from contextlib import contextmanager
import threading
import unittest
import subprocess
import shutil
import re
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
from json import dumps, loads
from pathlib import Path
from unittest.mock import patch

from uno_portal.host import broker
from uno_portal.python import main as web
from uno_portal import install as portal_install
from uno_portal.host import products


@contextmanager
def isolated_sleep(module, **kwargs):
    # Replace this module's clock, not the shared time.sleep used by live
    # Matrix/lease threads created by the imported broker.
    with patch.object(module, 'time') as clock:
        clock.sleep.configure_mock(**kwargs)
        yield clock.sleep


class ProductSocketDirectoryTests(unittest.TestCase):
    def test_creates_private_directory_and_repairs_mode(self):
        with tempfile.TemporaryDirectory() as directory:
            socket_dir = Path(directory) / "router"
            with patch.object(products, "SOCKET_DIR", socket_dir):
                products.ensure_socket_directory()
                self.assertEqual(socket_dir.stat().st_mode & 0o777, 0o700)
                socket_dir.chmod(0o755)
                products.ensure_socket_directory()
                self.assertEqual(socket_dir.stat().st_mode & 0o777, 0o700)

    def test_existing_socket_is_not_replaced(self):
        import socket
        with tempfile.TemporaryDirectory() as directory:
            socket_dir = Path(directory) / "router"
            socket_dir.mkdir(mode=0o700)
            path = socket_dir / "control.sock"
            with socket.socket(socket.AF_UNIX) as listener:
                listener.bind(str(path))
                inode = path.stat().st_ino
                with patch.object(products, "SOCKET_DIR", socket_dir):
                    products.ensure_socket_directory()
                self.assertEqual(path.stat().st_ino, inode)

    def test_rejects_directory_owned_by_another_user(self):
        with tempfile.TemporaryDirectory() as directory:
            socket_dir = Path(directory) / "router"
            socket_dir.mkdir()
            with patch.object(products, "SOCKET_DIR", socket_dir), \
                 patch.object(products.os, "getuid", return_value=-1):
                with self.assertRaisesRegex(RuntimeError, "not owned"):
                    products.ensure_socket_directory()

    def test_rejects_symlink_without_changing_target(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "other"
            target.mkdir(mode=0o755)
            socket_dir = root / "router"
            socket_dir.symlink_to(target, target_is_directory=True)
            with patch.object(products, "SOCKET_DIR", socket_dir):
                with self.assertRaises(OSError):
                    products.ensure_socket_directory()
            self.assertEqual(target.stat().st_mode & 0o777, 0o755)


class RepeatPortalInstallTests(unittest.TestCase):
    def test_static_payload_detects_same_version_hotfix(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / 'source'; installed = Path(directory) / 'installed'
            for root in (source, installed):
                (root / 'host').mkdir(parents=True)
                (root / 'VERSION').write_text('0.3.3\n')
                (root / 'host/products.py').write_text('old\n')
            self.assertTrue(portal_install.matching_static_payload(source, installed))
            (source / 'host/products.py').write_text('hotfix\n')
            self.assertFalse(portal_install.matching_static_payload(source, installed))
            (source / 'host/products.py').write_text('old\n')
            (source / 'install.py').write_text('new installer\n')
            (installed / 'install.py').write_text('old installer\n')
            self.assertFalse(portal_install.matching_static_payload(source, installed))
            self.assertTrue(portal_install.matching_static_payload(source, installed,
                                                                    exclude_quiet_updates=True))

    def test_private_running_matrix_and_both_http_endpoints_are_required(self):
        response = unittest.mock.MagicMock(); response.__enter__.return_value.status = 200
        good = subprocess.CompletedProcess([], 0, stdout=(
            'true|{"8123/tcp":[{"HostIp":"127.0.0.1","HostPort":"8123"}]}\n'))
        with patch.object(portal_install.subprocess, 'run', return_value=good), \
             patch.object(portal_install, 'urlopen', return_value=response) as request:
            self.assertTrue(portal_install.healthy_installed_portal())
            self.assertEqual([call.args[0] for call in request.call_args_list], [
                'http://127.0.0.1:8123/health', 'http://127.0.0.1/api/state'])
        for output in ('false|{"8123/tcp":[{"HostIp":"127.0.0.1","HostPort":"8123"}]}',
                       'true|{"8123/tcp":[{"HostIp":"0.0.0.0","HostPort":"8123"}]}'):
            with self.subTest(output=output), patch.object(portal_install.subprocess, 'run',
                                                       return_value=subprocess.CompletedProcess([], 0, stdout=output)), \
                 patch.object(portal_install, 'urlopen') as request:
                self.assertFalse(portal_install.healthy_installed_portal())
                request.assert_not_called()

    def test_identical_healthy_install_registers_products_without_app_lab(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); source = root / 'source'; installed = root / 'installed'
            source.mkdir(); installed.mkdir()
            (source / 'VERSION').write_text('0.3.3\n')
            (installed / 'VERSION').write_text('0.3.3\n')
            (source / 'install.py').write_text('same installer\n')
            (installed / 'install.py').write_text('same installer\n')
            for place in (source, installed):
                (place / 'host').mkdir()
                (place / 'host/products.py').write_text('same launcher\n')
            with patch.object(portal_install, 'SOURCE', source), patch.object(portal_install, 'DEST', installed), \
                 patch.object(portal_install.os, 'geteuid', return_value=1000), \
                 patch.object(portal_install, 'validate_package'), \
                 patch.object(portal_install, 'matching_static_payload', return_value=True), \
                 patch.object(portal_install, 'healthy_installed_portal', return_value=True), \
                 patch.object(portal_install, 'command') as command, \
                 patch.object(portal_install, 'app_listing') as listing, \
                 patch.object(portal_install, 'retire_early_start'):
                self.assertIn('healthy', portal_install.install())
                self.assertEqual(command.call_args_list[0].args,
                                 ('python3', str(installed / 'host/products.py'), 'start-all'))
                self.assertEqual(command.call_count, 3)
                listing.assert_not_called()

    def test_unhealthy_equal_version_enters_repair_path(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); source = root / 'source'; installed = root / 'installed'
            source.mkdir(); installed.mkdir()
            (source / 'VERSION').write_text('0.3.3\n')
            (installed / 'VERSION').write_text('0.3.3\n')
            (source / 'install.py').write_text('same installer\n')
            (installed / 'install.py').write_text('same installer\n')
            for place in (source, installed):
                (place / 'host').mkdir()
                (place / 'host/products.py').write_text('same launcher\n')
            with patch.object(portal_install, 'SOURCE', source), patch.object(portal_install, 'DEST', installed), \
                 patch.object(portal_install.os, 'geteuid', return_value=1000), \
                 patch.object(portal_install, 'validate_package'), \
                 patch.object(portal_install, 'matching_static_payload', return_value=True), \
                 patch.object(portal_install, 'healthy_installed_portal', return_value=False), \
                 patch.object(portal_install, 'app_listing', side_effect=RuntimeError('repair path')):
                with self.assertRaisesRegex(RuntimeError, 'repair path'):
                    portal_install.install()

    def test_installer_only_upgrade_is_atomic_and_skips_app_lab(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); source = root / 'source'; installed = root / 'installed'
            source.mkdir(); installed.mkdir()
            for place in (source, installed):
                (place / 'VERSION').write_text('0.3.3\n')
            (source / 'install.py').write_text('corrected installer\n')
            (installed / 'install.py').write_text('old installer\n')
            for place in (source, installed):
                (place / 'host').mkdir()
                (place / 'host/products.py').write_text('same launcher\n')
            with patch.object(portal_install, 'SOURCE', source), patch.object(portal_install, 'DEST', installed), \
                 patch.object(portal_install.os, 'geteuid', return_value=1000), \
                 patch.object(portal_install, 'validate_package'), \
                 patch.object(portal_install, 'healthy_installed_portal', return_value=True), \
                 patch.object(portal_install, 'command') as command, \
                 patch.object(portal_install, 'app_listing') as listing, \
                 patch.object(portal_install, 'retire_early_start'):
                self.assertIn('healthy', portal_install.install())
                listing.assert_not_called()
                self.assertEqual(command.call_count, 3)
            self.assertEqual((installed / 'install.py').read_text(), 'corrected installer\n')
            self.assertFalse(any(installed.glob('.router-update-*')))

    def test_installer_only_upgrade_rolls_back_on_registration_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); source = root / 'source'; installed = root / 'installed'
            source.mkdir(); installed.mkdir()
            for place in (source, installed):
                (place / 'VERSION').write_text('0.3.3\n')
            (source / 'install.py').write_text('corrected installer\n')
            old = installed / 'install.py'; old.write_text('old installer\n'); old.chmod(0o700)
            for place in (source, installed):
                (place / 'host').mkdir()
                (place / 'host/products.py').write_text('same launcher\n')

            def fail_registration(*args, **kwargs):
                self.assertEqual(old.read_text(), 'corrected installer\n')
                raise RuntimeError('registration failed')

            with patch.object(portal_install, 'SOURCE', source), patch.object(portal_install, 'DEST', installed), \
                 patch.object(portal_install.os, 'geteuid', return_value=1000), \
                 patch.object(portal_install, 'validate_package'), \
                 patch.object(portal_install, 'healthy_installed_portal', return_value=True), \
                 patch.object(portal_install, 'command', side_effect=fail_registration), \
                 patch.object(portal_install, 'app_listing') as listing:
                with self.assertRaisesRegex(RuntimeError, 'registration failed'):
                    portal_install.install()
                listing.assert_not_called()
            self.assertEqual(old.read_text(), 'old installer\n')
            self.assertEqual(old.stat().st_mode & 0o777, 0o700)
            self.assertFalse(any(installed.glob('.router-update-*')))

    def test_installer_and_product_launcher_update_together_and_roll_back_together(self):
        for fail in (False, True):
            with self.subTest(fail=fail), tempfile.TemporaryDirectory() as directory:
                root = Path(directory); source = root / 'source'; installed = root / 'installed'
                for place in (source, installed):
                    (place / 'host').mkdir(parents=True)
                    (place / 'VERSION').write_text('0.3.3\n')
                (source / 'install.py').write_text('new installer\n')
                (source / 'host/products.py').write_text('new launcher\n')
                old_installer = installed / 'install.py'
                old_launcher = installed / 'host/products.py'
                old_installer.write_text('old installer\n'); old_installer.chmod(0o700)
                old_launcher.write_text('old launcher\n'); old_launcher.chmod(0o600)

                def registration(*args, **kwargs):
                    self.assertEqual(old_installer.read_text(), 'new installer\n')
                    self.assertEqual(old_launcher.read_text(), 'new launcher\n')
                    if fail:
                        raise RuntimeError('registration failed')
                    return subprocess.CompletedProcess(args, 0)

                with patch.object(portal_install, 'SOURCE', source), patch.object(portal_install, 'DEST', installed), \
                     patch.object(portal_install.os, 'geteuid', return_value=1000), \
                     patch.object(portal_install, 'validate_package'), \
                     patch.object(portal_install, 'healthy_installed_portal', return_value=True), \
                     patch.object(portal_install, 'command', side_effect=registration), \
                     patch.object(portal_install, 'app_listing') as listing, \
                     patch.object(portal_install, 'retire_early_start'):
                    if fail:
                        with self.assertRaisesRegex(RuntimeError, 'registration failed'):
                            portal_install.install()
                    else:
                        self.assertIn('healthy', portal_install.install())
                    listing.assert_not_called()
                self.assertEqual(old_installer.read_text(),
                                 'old installer\n' if fail else 'new installer\n')
                self.assertEqual(old_launcher.read_text(),
                                 'old launcher\n' if fail else 'new launcher\n')
                if fail:
                    self.assertEqual(old_installer.stat().st_mode & 0o777, 0o700)
                    self.assertEqual(old_launcher.stat().st_mode & 0o777, 0o600)
                self.assertFalse(any(installed.glob('.router-update-*')))
                self.assertFalse(any(root.glob('.router-quiet-update-*')))

    def test_second_file_update_failure_restores_first_file(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); source = root / 'source'; installed = root / 'installed'
            for place in (source, installed):
                (place / 'host').mkdir(parents=True)
                (place / 'VERSION').write_text('0.3.3\n')
            (source / 'install.py').write_text('new installer\n')
            (source / 'host/products.py').write_text('new launcher\n')
            (installed / 'install.py').write_text('old installer\n')
            (installed / 'host/products.py').write_text('old launcher\n')
            original = portal_install.replace_static_file

            def fail_second(path, content, mode):
                if path.name == 'products.py':
                    raise OSError('second replacement failed')
                return original(path, content, mode)

            with patch.object(portal_install, 'SOURCE', source), patch.object(portal_install, 'DEST', installed), \
                 patch.object(portal_install.os, 'geteuid', return_value=1000), \
                 patch.object(portal_install, 'validate_package'), \
                 patch.object(portal_install, 'healthy_installed_portal', return_value=True), \
                 patch.object(portal_install, 'replace_static_file', side_effect=fail_second), \
                 patch.object(portal_install, 'command') as command:
                with self.assertRaisesRegex(OSError, 'second replacement failed'):
                    portal_install.install()
                command.assert_not_called()
            self.assertEqual((installed / 'install.py').read_text(), 'old installer\n')
            self.assertEqual((installed / 'host/products.py').read_text(), 'old launcher\n')


class BaseImageTests(unittest.TestCase):
    def test_portal_and_products_share_one_app_lab_base_image(self):
        # Each extra python-apps-base tag costs about 900 MB on the UNO Q.
        compose = Path(products.__file__).with_name('portal-compose.yaml').read_text()
        images = set(re.findall(r'^\s*image:\s*(\S+)\s*$', compose, re.M))
        self.assertEqual(images, {products.IMAGE})
        self.assertTrue(products.IMAGE.startswith('ghcr.io/arduino/app-bricks/python-apps-base:'))
        with patch.object(products.subprocess, 'check_output', return_value='192.0.2.5\n'):
            for name in products.PRODUCTS:
                services = products.clean_compose(name)['services'].values()
                self.assertEqual({service['image'] for service in services}, {products.IMAGE})


class MatrixComposePortTests(unittest.TestCase):







    def test_app_lab_long_form_is_restricted_and_other_services_unchanged(self):
        source = ('name: controller-router\nservices:\n  main:\n    ports:\n'
                  '      - mode: ingress\n        target: 8123\n'
                  '        published: "8123"\n        protocol: tcp\n'
                  '  other:\n    ports:\n      - 8123:8123\nnetworks:\n  default: {}\n')
        updated, changed = portal_install._matrix_loopback_compose(source)
        self.assertTrue(changed)
        self.assertIn('        protocol: tcp\n        host_ip: 127.0.0.1\n  other:', updated)
        self.assertIn('  other:\n    ports:\n      - 8123:8123\n', updated)
        self.assertEqual(portal_install._matrix_loopback_compose(updated), (updated, False))

    def test_legacy_short_and_already_restricted_forms(self):
        for value in ('8123:8123', '"8123:8123"'):
            source = 'services:\n  main:\n    ports:\n      - ' + value + '\n'
            updated, changed = portal_install._matrix_loopback_compose(source)
            self.assertTrue(changed)
            self.assertIn('127.0.0.1:8123:8123', updated)
            self.assertEqual(portal_install._matrix_loopback_compose(updated), (updated, False))

    def test_rejects_extra_public_binding_even_when_loopback_is_present(self):
        for extra in ('0.0.0.0:8123:8123', '8123:8123/udp', '9999:8123',
                      'mode: ingress\n        target: 8123\n        published: "8123"\n        host_ip: 0.0.0.0'):
            with self.subTest(extra=extra):
                source = ('services:\n  main:\n    ports:\n'
                          '      - 127.0.0.1:8123:8123\n      - ' + extra + '\n')
                with self.assertRaisesRegex(RuntimeError, "exactly one Matrix service port"):
                    portal_install._matrix_loopback_compose(source)

    def test_rejects_ambiguous_or_incompatible_bindings(self):
        for port in ('0.0.0.0:8123:8123', '8123:8123/udp', '8124:8123',
                     '8123:8123\n      - 8123:8123'):
            with self.subTest(port=port):
                source = 'services:\n  main:\n    ports:\n      - ' + port + '\n'
                with self.assertRaises(RuntimeError):
                    portal_install._matrix_loopback_compose(source)


class MatrixPortRecoveryTests(unittest.TestCase):
    def test_watchdog_inspects_actual_binding_only_after_acquiring_lock(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); matrix = root / 'controller-router'; matrix.mkdir()
            (matrix / '.cache').mkdir(); (matrix / '.cache/app-compose.yaml').write_text('services:\n  main:\n    image: test\n')
            (matrix / 'app.yaml').write_text('name: Matrix\n')
            locked = []

            @contextmanager
            def acquired(_lock):
                locked.append(True)
                try:
                    yield
                finally:
                    locked.pop()

            def inspect(args, **_kwargs):
                self.assertTrue(locked, 'container inspection must occur under the lifecycle lock')
                # Simulates an upgrade that made the binding healthy while this
                # watchdog was waiting for the lock.
                if '{{.State.Running}}' in args:
                    return subprocess.CompletedProcess(args, 0, stdout='true\n')
                return subprocess.CompletedProcess(args, 0, stdout='[{"HostIp":"127.0.0.1","HostPort":"8123"}]')

            with patch.object(broker, 'ROOT', root), patch.object(broker, 'MATRIX_STATE', root / 'state'), \
                 patch.object(broker, 'matrix_port_lock', acquired), \
                 patch.object(broker.subprocess, 'run', side_effect=inspect), \
                 patch.object(broker, 'configure_loopback') as configure:
                self.assertFalse(broker.ensure_matrix_port())
                configure.assert_not_called()

    def test_watchdog_waits_for_upgrade_then_does_not_recreate_healthy_container(self):
        from uno_portal.host.matrix_port import matrix_port_lock
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); matrix = root / 'controller-router'; matrix.mkdir()
            (matrix / '.cache').mkdir()
            (matrix / '.cache/app-compose.yaml').write_text('services:\n  main:\n    image: test\n')
            (matrix / 'app.yaml').write_text('name: Matrix\n')
            entered = threading.Event(); finished = threading.Event(); result = []
            def watchdog():
                entered.set()
                try:
                    result.append(broker.ensure_matrix_port())
                finally:
                    finished.set()
            with patch.object(broker, 'ROOT', root), patch.object(broker, 'MATRIX_STATE', root / 'state'), \
                 patch.object(broker.subprocess, 'run') as inspect, \
                 patch.object(broker, 'configure_loopback') as configure:
                inspect.side_effect = [subprocess.CompletedProcess([], 0, stdout='true\n'),
                                       subprocess.CompletedProcess([], 0, stdout='[{"HostIp":"127.0.0.1","HostPort":"8123"}]')]
                with matrix_port_lock(root / 'state/.matrix-port.lock'):
                    thread = threading.Thread(target=watchdog)
                    thread.start()
                    self.assertTrue(entered.wait(2))
                    self.assertFalse(finished.wait(0.1))
                    inspect.assert_not_called()
                thread.join(2)
                self.assertFalse(thread.is_alive())
                self.assertEqual(result, [False])
                configure.assert_not_called()


    def test_unpublished_app_gets_single_loopback_mapping(self):
        source = 'name: controller-router\nservices:\n  main:\n    image: example\n'
        updated, changed = portal_install._matrix_loopback_compose(source)
        self.assertTrue(changed)
        self.assertIn('    ports:\n      - "127.0.0.1:8123:8123"\n', updated)
        self.assertEqual(portal_install._matrix_loopback_compose(updated), (updated, False))
        self.assertNotIn('ports:', (portal_install.SOURCE / 'app/app.yaml').read_text())

    def test_recreation_is_idempotent_and_failed_recreation_restores_generated_file(self):
        from uno_portal.host.matrix_port import configure_loopback
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); compose = root / 'app-compose.yaml'; lock = root / 'data/port.lock'
            source = 'services:\n  main:\n    image: example\n'; compose.write_text(source)
            runner = unittest.mock.Mock(side_effect=subprocess.CalledProcessError(1, ['docker']))
            with self.assertRaises(subprocess.CalledProcessError):
                configure_loopback(compose, lock, runner)
            self.assertEqual(compose.read_text(), source)
            runner.side_effect = None
            self.assertTrue(configure_loopback(compose, lock, runner))
            self.assertFalse(configure_loopback(compose, lock, runner))
            self.assertEqual(runner.call_count, 2)

    def test_installer_configures_loopback_without_relocking_lifecycle_lock(self):
        from uno_portal.host.matrix_port import configure_loopback, matrix_port_lock
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); compose = root / 'app-compose.yaml'; lock = root / 'state/port.lock'
            compose.write_text('services:\n  main:\n    image: example\n')
            runner = unittest.mock.Mock()
            with matrix_port_lock(lock):
                self.assertTrue(configure_loopback(compose, lock, runner, lock_held=True))
            runner.assert_called_once()
            self.assertIn('127.0.0.1:8123:8123', compose.read_text())

    def test_broker_waits_for_running_container_and_rejects_published_descriptor(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); matrix = root / 'controller-router'; matrix.mkdir()
            (matrix / '.cache').mkdir(); (matrix / '.cache/app-compose.yaml').write_text('services:\n  main:\n    image: test\n')
            (matrix / 'app.yaml').write_text('name: Matrix\n')
            with patch.object(broker, 'ROOT', root), patch.object(broker, 'MATRIX_STATE', root / 'state'), \
                 patch.object(broker.subprocess, 'run') as run, patch.object(broker, 'configure_loopback', return_value=True) as apply:
                run.return_value = subprocess.CompletedProcess([], 0, stdout='false\n')
                self.assertFalse(broker.ensure_matrix_port())
                apply.assert_not_called()
                run.side_effect = [subprocess.CompletedProcess([], 0, stdout='true\n'),
                                   subprocess.CompletedProcess([], 0, stdout='null\n')]
                self.assertTrue(broker.ensure_matrix_port())
                apply.assert_called_once()
                self.assertTrue(apply.call_args.kwargs["lock_held"])
                (matrix / 'app.yaml').write_text('name: Matrix\nports:\n  - 8123\n')
                with self.assertRaisesRegex(RuntimeError, 'must not publish'):
                    broker.ensure_matrix_port()

    def test_broker_leaves_healthy_loopback_binding_untouched(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); matrix = root / 'controller-router'; matrix.mkdir()
            (matrix / '.cache').mkdir(); (matrix / '.cache/app-compose.yaml').write_text('services:\n  main:\n    image: test\n')
            (matrix / 'app.yaml').write_text('name: Matrix\n')
            with patch.object(broker, 'ROOT', root), patch.object(broker, 'MATRIX_STATE', root / 'state'), \
                 patch.object(broker.subprocess, 'run') as run, patch.object(broker, 'configure_loopback') as apply:
                run.side_effect = [subprocess.CompletedProcess([], 0, stdout='true\n'),
                                   subprocess.CompletedProcess([], 0, stdout='[{"HostIp":"127.0.0.1","HostPort":"8123"}]')]
                self.assertFalse(broker.ensure_matrix_port())
                apply.assert_not_called()



    def test_missing_ports_are_recreated_after_interrupted_prior_recreation(self):
        from uno_portal.host.matrix_port import configure_loopback
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); compose = root / 'app-compose.yaml'
            compose.write_text('services:\n  main:\n    ports:\n      - "127.0.0.1:8123:8123"\n')
            runner = unittest.mock.Mock()
            self.assertTrue(configure_loopback(compose, root / 'data/port.lock', runner, force=True))
            runner.assert_called_once()

    def test_inline_empty_ports_are_restricted_and_duplicates_rejected(self):
        source = 'services:\n  main:\n    ports: []\n    image: test\n'
        modified, changed = portal_install._matrix_loopback_compose(source)
        self.assertTrue(changed)
        self.assertIn('127.0.0.1:8123:8123', modified)
        with self.assertRaisesRegex(RuntimeError, 'Duplicate Matrix ports'):
            portal_install._matrix_loopback_compose(source + '    ports:\n      - 8123:8123\n')

    def test_restart_rechecks_game_state_after_lock_and_defers(self):
        from uno_portal.host.matrix_port import configure_loopback
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); compose = root / 'app-compose.yaml'
            source = 'services:\n  main:\n    image: test\n'; compose.write_text(source)
            runner = unittest.mock.Mock()
            self.assertFalse(configure_loopback(compose, root / 'state/port.lock', runner,
                                                safe_to_restart=lambda: False))
            self.assertEqual(compose.read_text(), source)
            runner.assert_not_called()

    def test_uncertain_installed_product_game_state_fails_safe(self):
        from unittest.mock import MagicMock
        with tempfile.TemporaryDirectory() as directory:
            app = Path(directory) / 'rob-vision'; app.mkdir(); (app / 'app.yaml').write_text('name: test')
            apps = {'rob_vision': {'path': app, 'url': 'http://example.test'}}
            response = MagicMock(); response.__enter__.return_value = response
            with patch.object(broker, 'APPS', apps), patch.object(broker, 'urlopen') as request:
                request.side_effect = OSError('offline')
                self.assertTrue(broker.matrix_recreation_unsafe())
                request.side_effect = None; request.return_value = response
                for payload, expected in ((b'{}', True), (b'[]', True), (b'{"live_game_active":true}', True),
                                          (b'{"live_game_active":false}', False)):
                    response.read.return_value = payload
                    self.assertEqual(broker.matrix_recreation_unsafe(), expected)

    def test_watchdog_defers_active_game_and_retries_failure(self):
        game = unittest.mock.Mock(side_effect=[True, False, False])
        with patch.object(broker, 'ensure_matrix_port', side_effect=[RuntimeError('retry'), None]) as ensure, \
             isolated_sleep(broker, side_effect=[None, None, StopIteration]), \
             patch('builtins.print') as report:
            with self.assertRaises(StopIteration):
                broker.reconcile_matrix_port(game)
        self.assertEqual(ensure.call_count, 2)
        report.assert_called_once()


class CommandDiagnosticTests(unittest.TestCase):
    def test_failure_keeps_both_streams_and_redacts_sensitive_values(self):
        result = subprocess.CompletedProcess(['arduino-app-cli'], 1,
            stdout='OpenOCD: unable to open GPIO line 38\npassword=do-not-print\nprivate-unlabelled-output\n',
            stderr='Upload port watcher closed\nAuthorization: Bearer do-not-print\n')
        with patch.object(portal_install.subprocess, 'run', return_value=result):
            with self.assertRaises(RuntimeError) as failure:
                portal_install.command('arduino-app-cli', 'app', 'start')
        message = str(failure.exception)
        self.assertIn('stdout: OpenOCD: unable to open GPIO line 38', message)
        self.assertIn('stderr: Upload port watcher closed', message)
        self.assertNotIn('do-not-print', message)
        self.assertNotIn('private-unlabelled-output', message)
        self.assertIn('[sensitive diagnostic redacted]', message)

    def test_failure_redacts_private_keys_urls_and_unlabelled_tokens(self):
        payload = ('-----BEGIN PRIVATE KEY-----\nprivate-material\n-----END PRIVATE KEY-----\n'
                   'https://alice:hunter2@example.test\n' + 'A' * 40)
        result = subprocess.CompletedProcess(['tool'], 1, stdout='', stderr=payload)
        with patch.object(portal_install.subprocess, 'run', return_value=result):
            with self.assertRaises(RuntimeError) as failure:
                portal_install.command('tool', 'sensitive-argument')
        message = str(failure.exception)
        for secret in ('private-material', 'hunter2', 'A' * 40, 'sensitive-argument'):
            self.assertNotIn(secret, message)


class PortTests(unittest.TestCase):
    def test_entry_start_waits_for_router_api_without_recreating_a_healthy_page(self):
        with tempfile.TemporaryDirectory() as directory:
            portal = Path(directory)
            compose = portal / 'host/portal-compose.yaml'
            compose.parent.mkdir()
            compose.write_text('services: {}\n')
            with patch.object(broker, 'PORTAL', portal), \
                 patch.object(broker, 'portal_ready', side_effect=[False, False, True]), \
                 patch.object(broker.subprocess, 'run') as run, \
                 isolated_sleep(broker) as pause:
                broker.ensure_portal()
            run.assert_called_once()
            command = run.call_args[0][0]
            self.assertEqual(command[-2:], ['up', '-d'])
            self.assertNotIn('--force-recreate', command)
            pause.assert_called_once_with(1)
            with patch.object(broker, 'portal_ready', return_value=True), \
                 patch.object(broker.subprocess, 'run') as run:
                broker.ensure_portal()
            run.assert_not_called()

    def test_entry_start_reports_a_docker_port_conflict(self):
        with tempfile.TemporaryDirectory() as directory:
            portal = Path(directory)
            compose = portal / 'host/portal-compose.yaml'
            compose.parent.mkdir()
            compose.write_text('services: {}\n')
            conflict = subprocess.CalledProcessError(1, ['docker', 'compose'],
                                                     stderr='Bind for 0.0.0.0:80 failed: port is already allocated\n')
            with patch.object(broker, 'PORTAL', portal), \
                 patch.object(broker, 'portal_ready', return_value=False), \
                 patch.object(broker.subprocess, 'run', side_effect=conflict):
                with self.assertRaisesRegex(RuntimeError, 'port is already allocated'):
                    broker.ensure_portal()

    def test_entry_watchdog_retries_after_a_failed_start(self):
        with patch.object(broker, 'ensure_portal', side_effect=[RuntimeError('port busy'), None]) as ensure, \
             isolated_sleep(broker, side_effect=[None, StopIteration]) as pause, \
             patch('builtins.print') as report:
            with self.assertRaises(StopIteration):
                broker.start_portal()
        self.assertEqual(ensure.call_count, 2)
        self.assertEqual(pause.call_count, 2)
        report.assert_called_once_with('Controller Router entry unavailable: port busy', flush=True)

    def test_entry_health_requires_the_router_api(self):
        from io import BytesIO
        from urllib.error import URLError
        for payload, status, expected in [
            (b'{"apps": {}, "matrix": {}}', 200, True),
            (b'{"apps": {}}', 200, False),
            (b'[]', 200, False),
            (b'not json', 200, False),
            (b'{"apps": {}, "matrix": {}}', 503, False),
        ]:
            with self.subTest(payload=payload, status=status):
                response = BytesIO(payload)
                response.status = status
                with patch.object(broker, 'urlopen', return_value=response) as request:
                    self.assertEqual(broker.portal_ready(), expected)
                request.assert_called_once_with('http://127.0.0.1/api/state', timeout=2)
        with patch.object(broker, 'urlopen', side_effect=URLError('offline')):
            self.assertFalse(broker.portal_ready())

    def test_entry_start_has_a_bounded_readiness_wait(self):
        with tempfile.TemporaryDirectory() as directory:
            portal = Path(directory)
            compose = portal / 'host/portal-compose.yaml'
            compose.parent.mkdir()
            compose.write_text('services: {}\n')
            with patch.object(broker, 'PORTAL', portal), \
                 patch.object(broker, 'portal_ready', return_value=False) as ready, \
                 patch.object(broker.subprocess, 'run') as run, \
                 isolated_sleep(broker) as pause:
                with self.assertRaisesRegex(RuntimeError, 'port 80 did not respond'):
                    broker.ensure_portal()
            self.assertEqual(ready.call_count, 11)
            self.assertEqual(pause.call_count, 10)
            run.assert_called_once_with(
                ['docker', 'compose', '-p', broker.ENTRY_PROJECT, '-f', str(compose), 'up', '-d'],
                check=True, capture_output=True, text=True, timeout=90)

    def test_entry_watchdog_deduplicates_errors_and_recovers(self):
        failures = [OSError('offline'), OSError('offline'), None, OSError('offline')]
        with patch.object(broker, 'ensure_portal', side_effect=failures), \
             isolated_sleep(broker, side_effect=[None, None, None, StopIteration]), \
             patch('builtins.print') as report:
            with self.assertRaises(StopIteration):
                broker.start_portal()
        self.assertEqual(report.call_count, 2)

    def test_legacy_boot_cleanup_is_narrow_and_repeatable(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            unit = home / '.config/systemd/user/virtualglove-early-start.service'
            trial = unit.with_name('virtualglove-early-start-trial.service')
            helper = home / '.local/lib/virtualglove/uno-q-early-start.py'
            for path in (unit, trial, helper):
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text('obsolete')
            current = unit.with_name('controller-router-products.service')
            current.write_text('current')
            other = helper.with_name('keep.py')
            other.write_text('unrelated')
            with patch.object(portal_install, 'HOME', home), patch.object(portal_install, 'command') as command:
                portal_install.retire_early_start()
                count = command.call_count
                portal_install.retire_early_start()
                self.assertEqual(command.call_count, count)
                command.assert_any_call('systemctl', '--user', 'disable', '--now', unit.name, check=False)
            self.assertTrue(all(not path.exists() for path in (unit, trial, helper)))
            self.assertEqual(current.read_text(), 'current')
            self.assertEqual(other.read_text(), 'unrelated')

    def test_secure_setup_can_be_ready_after_http(self):
        from unittest.mock import MagicMock
        response = MagicMock()
        response.__enter__.return_value.status = 200
        with patch.object(portal_install, 'urlopen', side_effect=[OSError('starting'), response]) as open_url, \
             isolated_sleep(portal_install) as pause:
            portal_install.wait_secure_setup()
        self.assertEqual(open_url.call_count, 2)
        pause.assert_called_once_with(1)

    def test_secure_setup_readiness_has_a_deadline(self):
        with patch.object(portal_install, 'urlopen', side_effect=OSError('unavailable')) as open_url, \
             isolated_sleep(portal_install):
            with self.assertRaisesRegex(RuntimeError, 'secure Setup'):
                portal_install.wait_secure_setup()
        self.assertEqual(open_url.call_count, 30)

    def test_matrix_replacement_failure_restores_previous_app(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            matrix = root / 'matrix'; matrix.mkdir()
            (matrix / 'previous').write_text('working firmware')
            real_replace = portal_install.os.replace
            def replace(source, destination):
                if Path(source).name == 'matrix-stage':
                    raise OSError('replacement failed')
                return real_replace(source, destination)
            with patch.object(portal_install, 'MATRIX', matrix), \
                 patch.object(portal_install, 'MATRIX_STATE', root / 'state'), \
                 patch.object(portal_install, 'command'), \
                 patch.object(portal_install.os, 'replace', side_effect=replace):
                with self.assertRaisesRegex(OSError, 'replacement failed'):
                    portal_install.install_matrix_app()
            self.assertEqual((matrix / 'previous').read_text(), 'working firmware')

    def _matrix_source(self, root):
        source = root / 'source'
        (source / 'app/sketch').mkdir(parents=True)
        (source / 'app/python').mkdir()
        for name in ('VERSION', 'app.yaml', 'sketch/sketch.ino', 'sketch/sketch.yaml', 'python/main.py'):
            (source / 'app' / name).write_text('new ' + name)
        return source

    def test_matrix_upgrade_keeps_the_sketch_build_cache(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            matrix = root / 'matrix'
            (matrix / '.cache/sketch/core').mkdir(parents=True)
            (matrix / '.cache/sketch/core/core.a').write_text('compiled core')
            (matrix / '.cache/app-compose.yaml').write_text('regenerated by App Lab')
            with patch.object(portal_install, 'SOURCE', self._matrix_source(root)), \
                 patch.object(portal_install, 'MATRIX', matrix), \
                 patch.object(portal_install, 'MATRIX_STATE', root / 'state'), \
                 patch.object(portal_install, 'command'):
                backup, changed = portal_install.install_matrix_app()
            self.assertTrue(changed)
            self.assertEqual((matrix / '.cache/sketch/core/core.a').read_text(), 'compiled core')
            self.assertFalse((matrix / '.cache/app-compose.yaml').exists())
            self.assertEqual((matrix / 'sketch/sketch.ino').read_text(), 'new sketch/sketch.ino')
            self.assertTrue((backup / '.cache/sketch/core/core.a').is_file())

    def test_retry_after_failed_first_install_reuses_that_build(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            failed = root / 'state/matrix-failed/.cache/sketch'
            failed.mkdir(parents=True)
            (failed / 'sketch.ino.elf').write_text('compiled sketch')
            with patch.object(portal_install, 'SOURCE', self._matrix_source(root)), \
                 patch.object(portal_install, 'MATRIX', root / 'matrix'), \
                 patch.object(portal_install, 'MATRIX_STATE', root / 'state'), \
                 patch.object(portal_install, 'command'):
                portal_install.install_matrix_app()
            self.assertEqual((root / 'matrix/.cache/sketch/sketch.ino.elf').read_text(), 'compiled sketch')

    def test_matrix_start_retries_only_a_failed_flash(self):
        flash = RuntimeError('arduino-app-cli failed (exit 1): stderr: '
                             'level=error msg="Upload port detection failed, watcher closed"\n'
                             '[ERROR] Failed uploading: uploading error: exit status 1')
        calls = []
        def command(*args, check=True):
            calls.append(args[:3])
            if args[:3] == ('arduino-app-cli', 'app', 'start') and calls.count(args[:3]) == 1:
                raise flash
        with patch.object(portal_install, 'command', side_effect=command), \
             isolated_sleep(portal_install), patch('builtins.print'):
            portal_install.start_matrix_app()
        self.assertEqual(calls, [('arduino-app-cli', 'app', 'start'),
                                 ('arduino-app-cli', 'app', 'stop'),
                                 ('arduino-app-cli', 'app', 'start')])

        compile_error = RuntimeError('arduino-app-cli failed (exit 1): stderr: sketch.ino:3: error')
        with patch.object(portal_install, 'command', side_effect=compile_error) as once, \
             isolated_sleep(portal_install):
            with self.assertRaisesRegex(RuntimeError, 'sketch.ino:3'):
                portal_install.start_matrix_app()
        self.assertEqual(once.call_count, 1)

        calls.clear()
        def always_fails(*args, check=True):
            calls.append(args[:3])
            if args[:3] == ('arduino-app-cli', 'app', 'start'):
                raise flash
        with patch.object(portal_install, 'command', side_effect=always_fails), \
             isolated_sleep(portal_install), patch('builtins.print'):
            with self.assertRaisesRegex(RuntimeError, 'Failed uploading'):
                portal_install.start_matrix_app()
        self.assertEqual(calls.count(('arduino-app-cli', 'app', 'start')), 3)
        self.assertEqual(calls.count(('arduino-app-cli', 'app', 'stop')), 2)

    def test_failed_upgrade_restores_both_units_and_product_startup(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            host = root / 'old/host'; host.mkdir(parents=True)
            units = root / 'units'; units.mkdir()
            service = units / 'controller-router-portal.service'
            product = units / 'controller-router-products.service'
            for unit in (service, product):
                (host / unit.name).write_text('previous unit ' + unit.name)
                unit.write_text('failed candidate unit')
            with patch.object(portal_install, 'DEST', host.parent), \
                 patch.object(portal_install, 'SERVICE', service), \
                 patch.object(portal_install, 'PRODUCT_SERVICE', product), \
                 patch.object(portal_install, 'command') as command:
                portal_install.restore_services()
            for unit in (service, product):
                self.assertEqual(unit.read_text(), (host / unit.name).read_text())
                self.assertIn(unittest.mock.call('systemctl', '--user', 'start', unit.name, check=False), command.call_args_list)
            self.assertEqual(command.call_args_list[0], unittest.mock.call('systemctl', '--user', 'daemon-reload', check=False))

    def test_installer_requires_and_copies_both_companion_images(self):
        with tempfile.TemporaryDirectory() as directory:
            staged = Path(directory) / 'launcher'
            shutil.copytree(portal_install.SOURCE, staged,
                            ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
            portal_install.validate_package(staged)
            for name in ('pixel-pal.png', 'buddy.png'):
                asset = staged / 'python/assets' / name
                original = (portal_install.SOURCE / 'python/assets' / name).read_bytes()
                self.assertEqual(asset.read_bytes(), original)
                asset.unlink()
                with self.assertRaisesRegex(RuntimeError, name):
                    portal_install.validate_package(staged)
                asset.write_bytes(b'')
                with self.assertRaisesRegex(RuntimeError, name):
                    portal_install.validate_package(staged)
                asset.write_bytes(original)

            help_page = staged / 'python/help.html'
            help_page.unlink()
            with self.assertRaisesRegex(RuntimeError, 'python/help.html'):
                portal_install.validate_package(staged)

    def test_web_ports_are_migrated_without_rewriting_other_ports(self):
        for app_id, original, expected in (
            ("virtualglove", "    - 80:8088\n    - 8088:8088\n    - 8443:8443\n",
             "    - 127.0.0.1:8088:8088\n    - 8100:8088\n    - 8443:8443\n"),
            ("rob_vision", "    - 80:80\n    - 8766:8766\n",
             "    - 8766:8766\n    - 8101:8766\n"),
        ):
            with self.subTest(app=app_id), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                cache = root / ".cache"
                cache.mkdir()
                compose = cache / "app-compose.yaml"
                compose.write_text("services:\n  main:\n    ports:\n" + original)
                apps = dict(broker.APPS)
                apps[app_id] = dict(apps[app_id], path=root)
                with patch.object(broker, "APPS", apps), patch.object(broker.subprocess, "run") as run:
                    broker.configure_ports(app_id)
                    self.assertEqual(compose.read_text(), "services:\n  main:\n    ports:\n" + expected)
                    broker.configure_ports(app_id)
                    self.assertEqual(run.call_count, 1)


class SwitchTests(unittest.TestCase):
    def test_host_uses_running_services_without_app_lab_switching(self):
        from uno_portal.host.concurrent import ConcurrentLauncher
        self.assertIsInstance(broker.LAUNCHER, ConcurrentLauncher)


class WebTests(unittest.TestCase):
    def test_chooser_opens_running_services_and_serves_both_companions(self):
        page = web.PAGE.read_text()
        self.assertIn("Opening ' + names[key].name", page)
        self.assertNotIn("Starting ' + names[key]", page)
        self.assertIn("/assets/pixel-pal.png", page)
        self.assertIn("/assets/buddy.png", page)
        self.assertIn("port === 8101 ? '/dashboard/' : '/dashboard'", page)
        server = ThreadingHTTPServer(("127.0.0.1", 0), web.Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            for path, kind in (("/", "text/html"), ("/setup", "text/html"),
                               ("/help", "text/html"), ("/help.html", "text/html"),
                               ("/assets/pixel-pal.png", "image/png"),
                               ("/assets/buddy.png", "image/png")):
                with self.subTest(path=path):
                    conn = HTTPConnection("127.0.0.1", server.server_address[1])
                    conn.request("GET", path)
                    response = conn.getresponse()
                    self.assertEqual(response.status, 200)
                    self.assertIn(kind, response.getheader("Content-Type"))
                    self.assertTrue(response.read())
                    conn.close()
            with patch.object(web, 'ASSETS', Path('/nonexistent-router-assets')):
                conn = HTTPConnection('127.0.0.1', server.server_address[1])
                conn.request('GET', '/assets/buddy.png')
                response = conn.getresponse()
                self.assertEqual(response.status, 503)
                response.read(); conn.close()
        finally:
            server.shutdown()
            server.server_close()

    def test_help_is_directly_available_and_every_guide_link_works(self):
        server = ThreadingHTTPServer(("127.0.0.1", 0), web.Handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            conn = HTTPConnection("127.0.0.1", server.server_address[1])
            conn.request("GET", "/help")
            response = conn.getresponse()
            self.assertEqual(response.status, 200)
            help_page = response.read().decode()
            self.assertIn("Get ready to play", help_page)
            guides = set(re.findall(r'href="(/guides/Controller-Router-[^"]+\.pdf)"', help_page))
            self.assertEqual(len(guides), 5)
            for path in guides:
                with self.subTest(guide=path):
                    conn.request("GET", path)
                    guide = conn.getresponse()
                    self.assertEqual(guide.status, 200)
                    self.assertEqual(guide.getheader("Content-Type"), "application/pdf")
                    self.assertTrue(guide.read().startswith(b"%PDF-"))
            conn.close()
            for page in ("index.html", "setup.html", "trust.html"):
                self.assertIn('href="/help"', web.PAGE.with_name(page).read_text())
            self.assertIn("root+'help'", (web.PAGE.parent.parent / 'host/pairing.html').read_text())
        finally:
            server.shutdown()
            server.server_close()

    def test_pairing_trust_routes_are_public_only(self):
        server = ThreadingHTTPServer(('127.0.0.1', 0), web.Handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            with patch.object(web, 'broker', return_value={'certificate':'PUBLIC CERTIFICATE', 'fingerprint':'abc', 'token':'PRIVATE'}):
                for path in ('/pair', '/api/pairing-certificate', '/controller-router.crt'):
                    connection = HTTPConnection('127.0.0.1', server.server_address[1])
                    connection.request('GET', path)
                    response = connection.getresponse()
                    self.assertEqual(response.status, 200)
                    body = response.read().decode()
                    self.assertNotIn('PRIVATE', body)
                    if path == '/pair':
                        self.assertIn('Instructions for your device', body)
                        self.assertIn('data-platform="ios"', body)
                    if path == '/controller-router.crt':
                        self.assertEqual(body, 'PUBLIC CERTIFICATE')
                        self.assertIn('attachment', response.getheader('Content-Disposition'))
                    connection.close()
        finally:
            server.shutdown(); server.server_close()

    def test_iphone_profile_contains_only_this_public_certificate(self):
        import plistlib, ssl
        from uno_portal.host.secure_pairing import certificates, public_certificate
        with tempfile.TemporaryDirectory() as directory:
            certificates(Path(directory))
            public = public_certificate(directory)
            self.assertEqual(set(public), {'certificate', 'fingerprint'})
            server = ThreadingHTTPServer(('127.0.0.1', 0), web.Handler)
            threading.Thread(target=server.serve_forever, daemon=True).start()
            try:
                with patch.object(web, 'broker', return_value=public):
                    connection = HTTPConnection('127.0.0.1', server.server_address[1])
                    connection.request('GET', '/controller-router.mobileconfig')
                    response = connection.getresponse()
                    self.assertEqual(response.status, 200)
                    self.assertEqual(response.getheader('Content-Type'), 'application/x-apple-aspen-config')
                    profile = plistlib.loads(response.read()); connection.close()
                    self.assertEqual(len(profile['PayloadContent']), 1)
                    certificate = profile['PayloadContent'][0]
                    self.assertEqual(certificate['PayloadType'], 'com.apple.security.root')
                    self.assertEqual(certificate['PayloadContent'], ssl.PEM_cert_to_DER_cert(public['certificate']))
            finally:
                server.shutdown(); server.server_close()

    def test_http_entry_does_not_accept_pairing_credentials(self):
        server = ThreadingHTTPServer(('127.0.0.1', 0), web.Handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            with patch.object(web, 'broker') as call:
                connection = HTTPConnection('127.0.0.1', server.server_address[1])
                connection.request('POST', '/api/pairing', '{}', {'Content-Type':'application/json'})
                response = connection.getresponse()
                self.assertEqual(response.status, 404)
                response.read(); connection.close(); call.assert_not_called()
        finally:
            server.shutdown(); server.server_close()

    def test_setup_routing_rejects_cross_site_and_forwards_same_origin(self):
        server = ThreadingHTTPServer(("127.0.0.1", 0), web.Handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        port = server.server_address[1]
        try:
            with patch.object(web, 'broker', return_value={'targets':[]}) as call:
                for origin, status in [('http://evil.example',403), ('http://[invalid',403),
                                       (f'http://127.0.0.1:{port}',200)]:
                    connection=HTTPConnection('127.0.0.1',port)
                    connection.request('POST','/api/routing','{"operation":"targets"}',
                                       {'Content-Type':'application/json','Origin':origin})
                    response=connection.getresponse();self.assertEqual(response.status,status)
                    response.read();connection.close()
                call.assert_called_once_with({'action':'routing','operation':'targets'})
        finally:
            server.shutdown();server.server_close()

    def test_every_portal_page_links_to_secure_console_setup(self):
        pages = Path(web.__file__).parent
        for name in ('index.html', 'setup.html', 'help.html', 'trust.html'):
            with self.subTest(page=name):
                text = (pages / name).read_text()
                self.assertIn('>Console setup</a>', text)
                self.assertIn("':8444/setup'", text)

    def test_console_halt_relays_only_its_fields_and_reports_refusals(self):
        server = ThreadingHTTPServer(("127.0.0.1", 0), web.Handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        port = server.server_address[1]
        try:
            body = dumps({'operation': 'request', 'console_id': 'a' * 32, 'nonce': 'n',
                               'proof': 'p', 'action': 'select', 'app': 'virtualglove'})
            with patch.object(web, 'broker', side_effect=[{'halting': True}, {'error': 'refused'}]) as call:
                for status in (200, 400):
                    connection = HTTPConnection('127.0.0.1', port)
                    connection.request('POST', '/api/console-halt', body, {'Content-Type': 'application/json'})
                    response = connection.getresponse(); self.assertEqual(response.status, status)
                    response.read(); connection.close()
            # A smuggled "action" cannot turn a halt request into an app selection.
            call.assert_called_with({'action': 'console-halt', 'operation': 'request',
                                     'console_id': 'a' * 32, 'nonce': 'n', 'proof': 'p'})
            with patch.object(web, 'broker') as call:
                connection = HTTPConnection('127.0.0.1', port)
                connection.request('POST', '/api/console-halt', dumps({'pad': 'x' * 600}),
                                   {'Content-Type': 'application/json'})
                self.assertEqual(connection.getresponse().status, 400); connection.close()
                call.assert_not_called()
        finally:
            server.shutdown(); server.server_close()

    def test_cross_site_switch_is_rejected_and_same_origin_is_accepted(self):
        server = ThreadingHTTPServer(("127.0.0.1", 0), web.Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        port = server.server_address[1]
        try:
            with patch.object(web, "broker", return_value={"accepted": True}) as call:
                conn = HTTPConnection("127.0.0.1", port)
                conn.request("POST", "/api/select", '{"app":"virtualglove"}',
                             {"Content-Type": "application/json", "Origin": "http://evil.example"})
                response = conn.getresponse()
                self.assertEqual(response.status, 403)
                response.read()
                self.assertFalse(call.called)
                conn.close()
                conn = HTTPConnection("127.0.0.1", port)
                conn.request("POST", "/api/select", '{"app":"virtualglove"}',
                             {"Content-Type": "application/json", "Origin": f"https://127.0.0.1:{port}"})
                response = conn.getresponse()
                self.assertEqual(response.status, 403)
                response.read()
                self.assertFalse(call.called)
                conn.close()
                conn = HTTPConnection("127.0.0.1", port)
                conn.request("POST", "/api/select", '{"app":"virtualglove"}',
                             {"Content-Type": "application/json", "Origin": f"http://127.0.0.1:{port}"})
                response = conn.getresponse()
                self.assertEqual(response.status, 202)
                self.assertTrue(loads(response.read())["accepted"])
                conn.close()
                # Direct product pages select through a permitted local port.
                conn = HTTPConnection("127.0.0.1", port)
                conn.request("OPTIONS", "/api/select", headers={"Origin": "http://127.0.0.1:8101"})
                response = conn.getresponse()
                self.assertEqual(response.status, 204)
                self.assertEqual(response.getheader("Access-Control-Allow-Origin"),
                                 "http://127.0.0.1:8101")
                response.read()
                conn.close()
                conn = HTTPConnection("127.0.0.1", port)
                conn.request("POST", "/api/select", '{"app":"rob_vision"}',
                             {"Content-Type": "application/json", "Origin": "http://127.0.0.1:8101",
                              "Sec-Fetch-Site": "same-site"})
                response = conn.getresponse()
                self.assertEqual(response.status, 202)
                self.assertTrue(loads(response.read())["accepted"])
                conn.close()
        finally:
            server.shutdown()
            server.server_close()


class InstallerTests(unittest.TestCase):
    def test_start_marks_router_required_without_changing_product_settings(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            data = root / "rob-vision/data"
            data.mkdir(parents=True)
            settings = data / "controller-token"
            settings.write_text("saved-pairing\n")
            with patch.object(products, "ROOT", root), \
                 patch.object(products, "product_compose", return_value=root / "runtime.json"), \
                 patch.object(products.subprocess, "run"):
                products.start("rob-vision")
                products.start("rob-vision")
            self.assertEqual(settings.read_text(), "saved-pairing\n")
            self.assertEqual((data / "controller-router-required").read_text(), "1\n")

    def test_runtime_network_does_not_reuse_app_lab_network(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "virtualglove/.cache").mkdir(parents=True)
            (root / "virtualglove/.cache/app-compose.yaml").write_text("services: {}\n")
            cached = '{"name":"virtualglove","services":{"main":{"volumes":[]}},"networks":{"default":{"name":"virtualglove_default"}}}'
            with patch.object(products, "ROOT", root), \
                 patch.object(products, "RUNTIME", root / "runtime"), \
                 patch.object(products, "SOCKET_DIR", root / "socket"), \
                 patch.object(products.subprocess, "run") as run:
                run.return_value.stdout = cached
                output = products.product_compose("virtualglove")
            self.assertEqual(loads(output.read_text())["networks"]["default"]["name"],
                             "virtualglove-runtime_default")

    def test_runtime_moves_cached_app_lab_services_to_the_router_base_image(self):
        # An App Lab cache written before an App Lab update names the old image.
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "virtualglove/.cache").mkdir(parents=True)
            (root / "virtualglove/.cache/app-compose.yaml").write_text("services: {}\n")
            old = products.BASE_REPOSITORY + ":0.12.0"
            cached = {"services": {"main": {"image": old, "volumes": []},
                                   "avahi-resolver": {"image": old},
                                   "other": {"image": "example/other:1"}}}
            with patch.object(products, "ROOT", root), \
                 patch.object(products, "RUNTIME", root / "runtime"), \
                 patch.object(products, "SOCKET_DIR", root / "socket"), \
                 patch.object(products.subprocess, "run") as run:
                run.return_value.stdout = dumps(cached)
                output = products.product_compose("virtualglove")
            services = loads(output.read_text())["services"]
            self.assertEqual(services["main"]["image"], products.IMAGE)
            self.assertEqual(services["avahi-resolver"]["image"], products.IMAGE)
            self.assertEqual(services["other"]["image"], "example/other:1")

    def test_start_all_retires_only_older_unused_base_images(self):
        repository = products.BASE_REPOSITORY
        calls = []

        def docker(command, **_):
            calls.append(command[1:])
            result = subprocess.CompletedProcess(command, 0, "", "")
            if command[1:3] == ["image", "ls"]:
                result.stdout = "0.14.0\n0.13.2\n0.12.0\n0.11.1\nlatest\n"
            elif command[1] == "ps" and command[4] == f"ancestor={repository}:0.12.0":
                result.stdout = "abc rob-vision\ndef someone-else\nghi\n"
            elif command[1:3] == ["image", "rm"] and command[3].endswith(":0.11.1"):
                result.returncode = 1  # still used by a running container
            return result

        with patch.object(products.subprocess, "run", side_effect=docker):
            removed = products.retire_old_base_images()
        self.assertEqual(removed, [f"{repository}:0.12.0"])
        self.assertIn(["rm", "abc"], calls)
        self.assertFalse([call for call in calls if call[0] == "rm" and call != ["rm", "abc"]])
        attempted = [call[2] for call in calls if call[:2] == ["image", "rm"]]
        self.assertEqual(attempted, [f"{repository}:0.12.0", f"{repository}:0.11.1"])
        self.assertFalse([call for call in calls if "-f" in call or "--force" in call])
        with patch.object(products.subprocess, "run", side_effect=OSError("no docker")):
            self.assertEqual(products.retire_old_base_images(), [])

    def test_product_runtime_omits_only_stale_optional_led_binds(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "rob-vision/.cache").mkdir(parents=True)
            cached_file = root / "rob-vision/.cache/app-compose.yaml"
            cached_file.write_text("services: {}\n")
            present_led = root / "current-led"
            present_led.mkdir()
            volumes = [
                {"type": "bind", "source": "/sys/class/leds/retired-led",
                 "target": "/sys/class/leds/retired-led"},
                {"type": "bind", "source": str(present_led),
                 "target": "/sys/class/leds/current-led"},
                {"type": "bind", "source": "/nonexistent/product-data",
                 "target": "/app/data"},
            ]
            cached = {"services": {"main": {"volumes": volumes}}}
            with patch.object(products, "ROOT", root), \
                 patch.object(products, "RUNTIME", root / "runtime"), \
                 patch.object(products, "SOCKET_DIR", root / "socket"), \
                 patch.object(products.subprocess, "run") as run:
                run.return_value.stdout = dumps(cached)
                output = products.product_compose("rob-vision")
            runtime_volumes = loads(output.read_text())["services"]["main"]["volumes"]
            self.assertNotIn(volumes[0], runtime_volumes)
            self.assertIn(volumes[1], runtime_volumes)
            self.assertIn(volumes[2], runtime_volumes)
            self.assertEqual(cached_file.read_text(), "services: {}\n")

    def test_existing_led_bind_is_preserved(self):
        volume = {"type": "bind", "source": "/sys/class/leds/current-led",
                  "target": "/sys/class/leds/current-led"}
        with patch.object(products, "Path") as path:
            path.return_value.exists.return_value = True
            self.assertFalse(products._stale_led_bind(volume))
            path.assert_called_once_with(volume["source"])

    def test_matrix_upgrade_holds_watchdog_lock_through_swap_start_and_failure(self):
        import fcntl
        import os
        from uno_portal.host import secure_pairing

        for fail in (False, True):
            with self.subTest(fail=fail), tempfile.TemporaryDirectory() as directory:
                root = Path(directory); source = root / 'source'; (source / 'host').mkdir(parents=True)
                for name in ('controller-router-portal.service', 'controller-router-products.service'):
                    (source / 'host' / name).write_text('unit')
                (source / 'VERSION').write_text('0.3.3')
                state = root / 'state'; lock = state / '.matrix-port.lock'
                apps = {'rob_vision': {'name': 'R.O.B. Vision', 'path': root / 'rob-vision'}}
                def locked():
                    with lock.open('r+') as handle:
                        with self.assertRaises(BlockingIOError):
                            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                def swap():
                    locked()
                    return None, True
                def start(*, lock_held):
                    self.assertTrue(lock_held)
                    locked()
                    if fail:
                        raise RuntimeError('controlled start failure')
                response = unittest.mock.MagicMock(); response.__enter__.return_value.status = 200
                from contextlib import ExitStack
                patches = [
                    patch.object(portal_install, 'SOURCE', source),
                    patch.object(portal_install, 'DEST', root / 'portal'),
                    patch.object(portal_install, 'LEGACY', root / 'legacy'),
                    patch.object(portal_install, 'SERVICE', root / 'units/portal.service'),
                    patch.object(portal_install, 'PRODUCT_SERVICE', root / 'units/products.service'),
                    patch.object(portal_install, 'MATRIX_STATE', state),
                    patch.object(portal_install, 'MATRIX', root / 'matrix'),
                    patch.object(portal_install, 'APPS', apps),
                    patch.object(portal_install.os, 'geteuid', return_value=1000),
                    patch.object(portal_install, 'validate_package'),
                    patch.object(portal_install, 'app_listing', return_value={}),
                    patch.object(portal_install, 'command', side_effect=lambda *a, **k: subprocess.CompletedProcess(a, 0, stdout='{}')),
                    patch.object(secure_pairing, 'certificates'),
                    patch.object(portal_install, 'install_matrix_app', side_effect=swap),
                    patch.object(portal_install, 'start_shared_matrix', side_effect=start),
                    patch.object(portal_install, 'start_products'),
                    patch.object(portal_install, 'urlopen', return_value=response),
                    patch.object(portal_install, 'wait_secure_setup'),
                    patch.object(portal_install, 'retire_early_start', side_effect=RuntimeError('finished'))
                ]
                with ExitStack() as stack:
                    for item in patches:
                        stack.enter_context(item)
                    with self.assertRaisesRegex(RuntimeError, 'controlled start failure' if fail else 'finished'):
                        portal_install.install()
                with lock.open('r+') as handle:
                    fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)

    def test_older_bundle_never_downgrades_shared_launcher(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, installed = root / "source", root / "installed"
            source.mkdir()
            installed.mkdir()
            (source / "VERSION").write_text("0.1.0\n")
            (source / "host").mkdir()
            (source / "host/portal-compose.yaml").write_text("services: {}\n")
            (installed / "VERSION").write_text("0.2.0\n")
            with patch.object(portal_install, "SOURCE", source), \
                 patch.object(portal_install, "DEST", installed), \
                 patch.object(portal_install.os, "geteuid", return_value=1000), \
                 patch.object(portal_install, "command") as command:
                self.assertIn("newer", portal_install.install())
                self.assertEqual(command.call_args_list[0].args,
                                 ("python3", str(installed / "host/products.py"), "start-all"))
                self.assertEqual(len(command.call_args_list), 3)

    def test_older_bundles_preserve_040_portal_and_matrix(self):
        # 0.3.3 lacks Matrix-confirmed changes, 0.3.4 the lease fix, 0.3.5 halt on console shutdown.
        for older in ('0.3.2', '0.3.3', '0.3.4', '0.3.5'):
            with self.subTest(older=older), tempfile.TemporaryDirectory() as directory:
                root = Path(directory); source = root / 'old'; installed = root / 'current'
                source.mkdir(); installed.mkdir(); (source / 'VERSION').write_text(older + '\n')
                (installed / 'VERSION').write_text((portal_install.SOURCE / 'VERSION').read_text())
                self.assertEqual((installed / 'VERSION').read_text().strip(), '0.4.0')
                sentinel = installed / 'preserved'; sentinel.write_text('sentinel')
                with patch.object(portal_install, 'SOURCE', source), patch.object(portal_install, 'DEST', installed), \
                     patch.object(portal_install, 'LEGACY', root / 'legacy'), \
                     patch.object(portal_install.os, 'geteuid', return_value=1000), \
                     patch.object(portal_install, 'command'), patch.object(portal_install, 'validate_package') as validate, \
                     patch.object(portal_install, 'install_matrix_app') as matrix:
                    self.assertIn('newer', portal_install.install())
                    validate.assert_not_called(); matrix.assert_not_called()
                self.assertEqual(sentinel.read_text(), 'sentinel')

    def test_previous_stable_product_cannot_replace_prepared_runtime(self):
        current = (portal_install.SOURCE / 'VERSION').read_text()
        self.assertGreater(tuple(map(int, current.strip().split('.'))), (0, 3, 1))
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, installed = root / 'old-product', root / 'installed'
            source.mkdir()
            installed.mkdir()
            (source / 'VERSION').write_text('0.3.1\n')
            (installed / 'VERSION').write_text(current)
            sentinel = installed / 'preserved-runtime'
            sentinel.write_text('new recovery implementation')
            with patch.object(portal_install, 'SOURCE', source), \
                 patch.object(portal_install, 'DEST', installed), \
                 patch.object(portal_install, 'LEGACY', root / 'legacy'), \
                 patch.object(portal_install.os, 'geteuid', return_value=1000), \
                 patch.object(portal_install, 'command') as command, \
                 patch.object(portal_install, 'validate_package') as validate:
                self.assertIn('newer', portal_install.install())
                validate.assert_not_called()
                self.assertEqual(command.call_args_list[0][0],
                                 ('python3', str(installed / 'host/products.py'), 'start-all'))
            self.assertEqual(sentinel.read_text(), 'new recovery implementation')
            self.assertEqual((installed / 'VERSION').read_text(), current)

    def test_incomplete_bundle_fails_before_changing_services(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, installed = root / "source", root / "installed"
            (source / "host").mkdir(parents=True)
            (source / "host/portal-compose.yaml").write_text("services: {}\n")
            with patch.object(portal_install, "SOURCE", source), \
                 patch.object(portal_install, "DEST", installed), \
                 patch.object(portal_install, "LEGACY", root / "legacy"), \
                 patch.object(portal_install.os, "geteuid", return_value=1000), \
                 patch.object(portal_install, "command") as command, \
                 patch.object(portal_install, "app_listing") as listing:
                with self.assertRaisesRegex(RuntimeError, "sketch.yaml"):
                    portal_install.install()
                command.assert_not_called()
                listing.assert_not_called()
                self.assertFalse(installed.exists())


if __name__ == "__main__":
    unittest.main()
