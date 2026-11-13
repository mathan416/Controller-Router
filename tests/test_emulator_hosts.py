import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from router_shared import emulator_hosts


class EmulatorHostsTests(unittest.TestCase):
    def test_flycast_is_opt_in_and_preserves_analog(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = Path(tmp) / 'host.json'
            with patch.object(emulator_hosts, 'CONFIG', config):
                axes = {'lx': 123, 'ly': 0, 'hat_x': 1, 'hat_y': -1}
                self.assertEqual(emulator_hosts.transform_controls({'l1'}, axes, 'flycast-native', 'dreamcast'), ({'l1'}, axes))
                config.write_text(json.dumps({'schema': 1, 'flycast_dreamcast_controls': True}))
                buttons, result = emulator_hosts.transform_controls({'l1', 'r1'}, axes, 'flycast-native', 'dreamcast')
                self.assertEqual(buttons, {'l1', 'r1', 'l2', 'r2'})
                self.assertEqual(result['lx'], 123)
                self.assertEqual(result['ly'], -32768)
                self.assertEqual(emulator_hosts.transform_controls({'l1'}, axes, 'native-merged', 'arcade'), ({'l1'}, axes))

    def test_bad_loader_entries_are_ignored(self):
        with patch.object(emulator_hosts, 'read_config', return_value={'loader_sessions': [{}, None]}):
            self.assertEqual(emulator_hosts.native_session(), (None, None))
