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
    def test_zero_one_and_two_installed_states(self):
        launcher = broker.Launcher()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            apps = {key: dict(value, path=root / key) for key, value in broker.APPS.items()}
            with patch.object(broker, "APPS", apps), patch.object(broker, "app_listing") as listing:
                listing.return_value = {}
                self.assertEqual(sum(item["installed"] for item in launcher.state()["apps"].values()), 0)
                apps["virtualglove"]["path"].mkdir()
                (apps["virtualglove"]["path"] / "app.yaml").write_text("name: VirtualGlove\n")
                listing.return_value = {"VirtualGlove": "stopped"}
                self.assertEqual(sum(item["installed"] for item in launcher.state()["apps"].values()), 1)
                apps["rob_vision"]["path"].mkdir()
                (apps["rob_vision"]["path"] / "app.yaml").write_text("name: R.O.B. Vision\n")
                listing.return_value = {"VirtualGlove": "stopped", "R.O.B. Vision": "stopped"}
                self.assertEqual(sum(item["installed"] for item in launcher.state()["apps"].values()), 2)

    def test_game_blocks_switch_before_stopping_anything(self):
        launcher = broker.Launcher()
        actions = []
        with patch.object(broker, "app_listing", return_value={"VirtualGlove": "running", "R.O.B. Vision": "stopped"}), \
             patch.object(broker, "health", return_value=(True, True)), \
             patch.object(broker, "cli", side_effect=lambda *a, **k: actions.append(a)):
            launcher._switch("rob_vision")
        self.assertEqual(actions, [])
        self.assertIn("End the current game", launcher.error)

    def test_success_stops_previous_then_starts_target_and_saves_default(self):
        launcher = broker.Launcher()
        actions = []
        with patch.object(broker, "app_listing", return_value={"VirtualGlove": "running", "R.O.B. Vision": "stopped"}), \
             patch.object(broker, "health", side_effect=[(True, False), (True, False)]), \
             patch.object(broker, "configure_ports", side_effect=lambda key: actions.append(("ports", key))), \
             patch.object(broker, "cli", side_effect=lambda *a, **k: actions.append(a)):
            launcher._switch("rob_vision")
        self.assertEqual([entry[1] for entry in actions if entry[0] == "app"], ["stop", "start"])
        self.assertIn(("ports", "rob_vision"), actions)
        self.assertTrue(any(entry[:3] == ("properties", "set", "default") for entry in actions))
        self.assertEqual(launcher.error, "")

    def test_failed_target_start_restores_previous_controller(self):
        launcher = broker.Launcher()
        actions = []
        def app_command(*args, **_kwargs):
            actions.append(args)
            if args[:2] == ("app", "start") and args[2] == str(broker.APPS["rob_vision"]["path"]):
                raise subprocess.CalledProcessError(1, args)
        with patch.object(broker, "app_listing", return_value={"VirtualGlove": "running", "R.O.B. Vision": "stopped"}), \
             patch.object(broker, "health", return_value=(True, False)), \
             patch.object(broker, "configure_ports"), \
             patch.object(broker, "cli", side_effect=app_command):
            launcher._switch("rob_vision")
        self.assertEqual([item[1] for item in actions if item[0] == "app"],
                         ["stop", "start", "stop", "start"])
        self.assertTrue(any(item[:3] == ("properties", "set", "default") for item in actions))
        self.assertIn("returned non-zero", launcher.error)


class WebTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
