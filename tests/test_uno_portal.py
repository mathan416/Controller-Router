import tempfile
import threading
import unittest
import subprocess
import shutil
import re
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
from json import loads
from pathlib import Path
from unittest.mock import patch

from uno_portal.host import broker
from uno_portal.python import main as web
from uno_portal import install as portal_install
from uno_portal.host import products


class PortTests(unittest.TestCase):
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
             patch.object(portal_install.time, 'sleep') as pause:
            portal_install.wait_secure_setup()
        self.assertEqual(open_url.call_count, 2)
        pause.assert_called_once_with(1)

    def test_secure_setup_readiness_has_a_deadline(self):
        with patch.object(portal_install, 'urlopen', side_effect=OSError('unavailable')) as open_url, \
             patch.object(portal_install.time, 'sleep'):
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
                 patch.object(products.subprocess, "run") as run:
                run.return_value.stdout = cached
                output = products.product_compose("virtualglove")
            self.assertEqual(loads(output.read_text())["networks"]["default"]["name"],
                             "virtualglove-runtime_default")

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
