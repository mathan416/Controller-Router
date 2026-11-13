import unittest
from router_shared.computer_bridge import SamControls


class SamControlsTests(unittest.TestCase):
    def test_typing_toggle_and_release(self):
        controls = SamControls()
        axes = {'lx': 100, 'ly': -40}
        self.assertEqual(controls.apply({'hotkey'}, axes)[2], None)
        buttons, result, message = controls.apply({'a'}, axes)
        self.assertEqual((buttons, result, message), (set(), {'lx': 0, 'ly': 0}, 'FOCUS ON'))
        controls.apply({'hotkey'}, axes)
        self.assertEqual(controls.apply(set(), axes)[2], 'FOCUS OFF')
        self.assertEqual(controls.apply({'a'}, axes)[:2], ({'a'}, axes))

    def test_chord_and_exit(self):
        controls = SamControls()
        controls.apply({'hotkey'}, {'lx': 0})
        self.assertEqual(controls.apply({'hotkey', 'a'}, {'lx': 0})[2], None)
        self.assertIsNone(controls.apply(set(), {'lx': 0})[2])
        self.assertFalse(controls.typing)
        for buttons in ({'hotkey', 'start'}, {'select', 'start'}):
            self.assertEqual(controls.apply(buttons, {'lx': 10}), (set(), {'lx': 0}, 'EXIT'))

class OutputReadinessTests(unittest.TestCase):
    def test_waits_for_matching_joystick_and_rejects_duplicates(self):
        import tempfile
        from pathlib import Path
        from router_shared.computer_bridge import wait_for_output
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); sysroot = root / 'sys'; devroot = root / 'dev'
            devroot.mkdir(); device = sysroot / 'event1/device'; (device / 'id').mkdir(parents=True)
            (device / 'name').write_text('SAM Routed Player 1')
            (device / 'id/vendor').write_text('1209')
            (device / 'id/product').write_text('5753')
            (device / 'js0').touch(); (devroot / 'js0').touch()
            wait_for_output('SAM Routed Player 1', 0x5753, sysroot, devroot, .2)
            other = sysroot / 'event2'; other.mkdir(); (other / 'device').symlink_to(device, target_is_directory=True)
            with self.assertRaisesRegex(RuntimeError, 'Ambiguous'):
                wait_for_output('SAM Routed Player 1', 0x5753, sysroot, devroot, .2)
