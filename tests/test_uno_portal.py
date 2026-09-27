import tempfile
import threading
import unittest
import subprocess
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
            for path, kind in (("/", "text/html"),
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
        finally:
            server.shutdown()
            server.server_close()

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
