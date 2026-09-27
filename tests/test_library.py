import unittest
import json
import tempfile
from pathlib import Path
from unittest.mock import patch
from router_shared.controller_router import validate_config, output_name
from router_shared.merged_gamepad import controller_candidates
from router_shared.virtual_sources import configured_sources

class LibraryTests(unittest.TestCase):
    def test_player_bounds(self):
        self.assertEqual(output_name(2), "VirtualGlove Merged Player 2")
        with self.assertRaises(ValueError):
            output_name(5)

    def test_empty_virtual_sources(self):
        self.assertEqual(configured_sources(), [])

    def test_shared_schema(self):
        config = validate_config({"format": 2, "platform": "retropie",
                                  "players": [], "virtualglove_player": None})
        self.assertEqual(config["players"], [])

    def test_project_supplied_virtual_pad_uses_its_own_mapping(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            descriptor = root / "sources.json"
            descriptor.write_text(json.dumps({"schema": 1, "sources": [{
                "name": "Example Maker Pad", "vendor": "1209", "product": "0002",
                "mapping": [{"name": "a", "type": "button", "code": 0,
                             "value": 1, "evdev_code": 304}],
            }]}))
            device = {"name": "Example Maker Pad", "vendor": "1209", "product": "0002"}
            with patch("router_shared.merged_gamepad.input_devices", return_value=[device]):
                candidates = controller_candidates(root / "missing.xml", source_file=descriptor)
            self.assertEqual(candidates[0]["mapping"][0]["evdev_code"], 304)

    def test_virtual_source_file_rejects_wrong_schema(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sources.json"
            path.write_text('{"schema": 2, "sources": []}')
            with self.assertRaisesRegex(ValueError, "Unsupported"):
                configured_sources(path)
