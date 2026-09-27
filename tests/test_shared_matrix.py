import json
import io
import tempfile
import unittest
from contextlib import nullcontext
from pathlib import Path
from unittest.mock import patch

from uno_portal.display_protocol import load_manifest, validate_manifest
from uno_portal.host.concurrent import BOOT_ID, ConcurrentLauncher, lease_active
from uno_portal.host.display_runtime import MatrixScheduler, code_frame


class ManifestTests(unittest.TestCase):
    def test_both_exported_artworks_are_valid(self):
        root = Path(__file__).resolve().parents[2]
        paths = ((root / "rob-vision/matrix/manifest.json", "rob_vision"),
                 (root / "PowerGlove-launcher/matrix/manifest.json", "virtualglove"))
        for path, app in paths:
            with self.subTest(app=app):
                document = load_manifest(path, app)
                self.assertGreater(len(document["animations"]), 10)

    def test_rejects_wrong_dimensions_and_brightness(self):
        base = {"schema": 1, "app": "rob_vision", "animations": {
            "idle": {"loop": True, "frames": [{"ms": 100, "rows": ["0" * 13] * 8}]}}}
        self.assertEqual(validate_manifest(base, "rob_vision"), base)
        base["animations"]["idle"]["frames"][0]["rows"][1] = "8" * 13
        with self.assertRaises(ValueError):
            validate_manifest(base, "rob_vision")


class SchedulerTests(unittest.TestCase):
    def test_only_selected_app_can_play_and_expiry_returns_idle(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "manifest.json"
            path.write_text(json.dumps({"schema": 1, "app": "rob_vision", "animations": {
                "eyes": {"loop": True, "frames": [{"ms": 100, "rows": ["7" * 13] * 8}]}}}))
            sent = []
            scheduler = MatrixScheduler(send=lambda rows: sent.append(rows) or True, clock=lambda: 0)
            with patch("uno_portal.host.display_runtime.MANIFESTS", {"rob_vision": path}):
                denied = scheduler.submit({"version": 1, "app": "rob_vision", "action": "play", "animation": "eyes"})
                self.assertFalse(denied["accepted"])
                scheduler.select("rob_vision")
                self.assertTrue(scheduler.submit({"version": 1, "app": "rob_vision", "action": "play", "animation": "eyes"})["accepted"])
                scheduler.tick()
                self.assertEqual(sent[-1][0], "7" * 13)
                scheduler.select(None)
                self.assertIsNone(scheduler.frame())

    def test_pairing_frames_include_complete_identity_and_pin(self):
        scheduler = MatrixScheduler(send=lambda rows: True, clock=lambda: 0)
        scheduler.select("virtualglove")
        scheduler.submit({"version": 1, "app": "virtualglove", "action": "pairing",
                          "identity": "1ABCDEF", "pin": "012345"})
        self.assertEqual(scheduler.frame(0), code_frame("ID"))
        self.assertEqual(scheduler.frame(.9), code_frame("1AB"))
        self.assertEqual(scheduler.frame(2.7), code_frame("F"))
        self.assertEqual(scheduler.frame(5.4), code_frame("345"))
        self.assertIsNone(scheduler.frame(121))

    def test_status_and_play_request_expire_without_heartbeat(self):
        now = [0.0]
        scheduler = MatrixScheduler(send=lambda rows: True, clock=lambda: now[0])
        scheduler.select("virtualglove")
        status = {"version": 1, "app": "virtualglove", "action": "status", "text": "P2"}
        self.assertTrue(scheduler.submit(status)["accepted"])
        self.assertEqual(scheduler.frame(), code_frame("P2"))
        now[0] = 4
        self.assertTrue(scheduler.submit(status)["accepted"])
        now[0] = 8
        self.assertEqual(scheduler.frame(), code_frame("P2"))
        now[0] = 10
        self.assertIsNone(scheduler.frame())


class LeaseTests(unittest.TestCase):
    def test_game_sessions_select_automatically_and_return_to_neutral(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            apps = {key: {"path": root / key, "url": "http://unused", "port": port}
                    for key, port in (("virtualglove", 8100), ("rob_vision", 8101))}
            for app in apps.values():
                (app["path"] / "data").mkdir(parents=True)
                (app["path"] / "app.yaml").write_text("name: test\n")
            matrix = MatrixScheduler(send=lambda rows: True)
            with patch.object(ConcurrentLauncher, "_heartbeat", return_value=None), \
                 patch.object(matrix, "run", return_value=None):
                launcher = ConcurrentLauncher(apps=apps, matrix=matrix)
            games = set()
            with patch.object(launcher, "_health", side_effect=lambda app: (True, app in games)), \
                 patch.object(launcher, "_matrix_ready", return_value=True), \
                 patch("uno_portal.host.concurrent.time.sleep"):
                self.assertTrue(launcher.select("virtualglove")["accepted"])
                games.add("rob_vision")
                launcher._reconcile_games()
                self.assertEqual(launcher.selected, "rob_vision")
                self.assertEqual(matrix.selected, "rob_vision")
                self.assertFalse(lease_active(apps["virtualglove"]["path"] / "data/controller-router-lease.json"))
                self.assertTrue(lease_active(apps["rob_vision"]["path"] / "data/controller-router-lease.json"))
                self.assertIn("End the current game", launcher.select("virtualglove")["error"])
                games.clear()
                launcher._reconcile_games()
                self.assertIsNone(launcher.selected)
                self.assertIsNone(matrix.selected)
                games.add("virtualglove")
                launcher._reconcile_games()
                self.assertEqual(launcher.selected, "virtualglove")
                games.clear()
                launcher._reconcile_games()
                self.assertIsNone(launcher.selected)

    def test_two_active_games_never_get_an_input_lease(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            apps = {key: {"path": root / key, "url": "http://unused", "port": port}
                    for key, port in (("virtualglove", 8100), ("rob_vision", 8101))}
            for app in apps.values():
                (app["path"] / "data").mkdir(parents=True)
            matrix = MatrixScheduler(send=lambda rows: True)
            with patch.object(ConcurrentLauncher, "_heartbeat", return_value=None), \
                 patch.object(matrix, "run", return_value=None):
                launcher = ConcurrentLauncher(apps=apps, matrix=matrix)
            with patch.object(launcher, "_health", return_value=(True, True)):
                launcher._reconcile_games()
            self.assertIsNone(launcher.selected)
            self.assertIn("More than one", launcher.error)
            for app in apps.values():
                self.assertFalse(lease_active(app["path"] / "data/controller-router-lease.json"))

    def test_background_game_still_locks_selection(self):
        launcher = object.__new__(ConcurrentLauncher)
        launcher.apps = {
            "virtualglove": {"url": "http://vg/status", "path": Path("/missing")},
            "rob_vision": {"url": "http://rob/api/state", "path": Path("/missing")},
        }
        for app_id, state in (
            ("virtualglove", {"worker_running": True, "game_session_active": True}),
            ("rob_vision", {"live_game_active": True}),
        ):
            with self.subTest(app=app_id), patch("uno_portal.host.concurrent.urlopen",
                return_value=nullcontext(io.BytesIO(json.dumps(state).encode()))):
                self.assertEqual(launcher._health(app_id), (True, True))

    def test_missing_stale_and_revoked_lease_fail_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "lease.json"
            self.assertFalse(lease_active(path, 10))
            path.write_text(json.dumps({"schema": 1, "boot_id": BOOT_ID, "active": True, "until": 11}))
            self.assertTrue(lease_active(path, 10))
            self.assertFalse(lease_active(path, 12))
            path.write_text(json.dumps({"schema": 1, "boot_id": BOOT_ID, "active": False, "until": 20}))
            self.assertFalse(lease_active(path, 10))
            path.write_text('{"schema":1,"boot_id":"previous-boot","active":true,"until":999999}')
            self.assertFalse(lease_active(path, 10))

    def test_game_blocks_selection_and_reboot_starts_unselected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            apps = {key: {"path": root / key, "url": "http://unused", "port": port}
                    for key, port in (("virtualglove", 8100), ("rob_vision", 8101))}
            for app in apps.values():
                (app["path"] / "data").mkdir(parents=True)
                (app["path"] / "app.yaml").write_text("name: test\n")
            matrix = MatrixScheduler(send=lambda rows: True)
            with patch.object(ConcurrentLauncher, "_heartbeat", return_value=None), \
                 patch.object(matrix, "run", return_value=None):
                launcher = ConcurrentLauncher(apps=apps, matrix=matrix)
            self.assertIsNone(launcher.selected)
            self.assertFalse(lease_active(apps["virtualglove"]["path"] / "data/controller-router-lease.json"))
            with patch.object(launcher, "_matrix_ready", return_value=True), \
                 patch.object(launcher, "_health", side_effect=lambda app: (True, app == "virtualglove")):
                self.assertIn("End the current game", launcher.select("rob_vision")["error"])
            with patch.object(launcher, "_matrix_ready", return_value=True), \
                 patch.object(launcher, "_health", return_value=(True, False)), \
                 patch("uno_portal.host.concurrent.time.sleep"):
                self.assertTrue(launcher.select("rob_vision")["accepted"])
            self.assertTrue(lease_active(apps["rob_vision"]["path"] / "data/controller-router-lease.json"))


if __name__ == "__main__":
    unittest.main()
