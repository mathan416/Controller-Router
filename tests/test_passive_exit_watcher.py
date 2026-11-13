import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
from router_shared import passive_exit_watcher as watcher

MAPPING = [dict(name='hotkey', type='button', code=304, value=1),
           dict(name='start', type='button', code=305, value=1)]


class ChordTests(unittest.TestCase):
    def test_press_release_repeat_and_fresh_chord(self):
        tracker = watcher.ChordTracker(MAPPING)
        self.assertFalse(tracker.event(1, 304, 1))
        self.assertTrue(tracker.event(1, 305, 1))
        self.assertFalse(tracker.event(1, 305, 2))
        self.assertFalse(tracker.event(1, 305, 0))
        self.assertTrue(tracker.event(1, 305, 1))
        tracker.release()
        self.assertFalse(tracker.event(1, 305, 1))

    def test_sources_cannot_form_a_cross_controller_chord(self):
        first, second = watcher.ChordTracker(MAPPING), watcher.ChordTracker(MAPPING)
        self.assertFalse(first.event(1, 304, 1))
        self.assertFalse(second.event(1, 305, 1))
        self.assertTrue(first.event(1, 305, 1))

    def test_select_start_is_same_source_and_requires_two_controls(self):
        mapping = MAPPING + [dict(name='select', type='button', code=306, value=1)]
        first, second = watcher.ChordTracker(mapping), watcher.ChordTracker(mapping)
        self.assertFalse(first.event(1, 306, 1))
        self.assertFalse(second.event(1, 305, 1))
        self.assertTrue(first.event(1, 305, 1))
        self.assertFalse(watcher.distinct_chord([dict(name='select', type='button', code=305, value=1),
                                                dict(name='start', type='button', code=305, value=1)]))

    def test_disconnect_and_dropped_events_release_state(self):
        tracker = watcher.ChordTracker(MAPPING)
        tracker.event(1, 304, 1)
        tracker.release()
        self.assertFalse(tracker.event(1, 305, 1))
        tracker.event(0, 3, 0)
        self.assertFalse(tracker.event(1, 304, 1))
        self.assertFalse(tracker.event(1, 305, 1))
        tracker.event(0, 0, 0)
        self.assertFalse(tracker.event(1, 304, 1))
        self.assertTrue(tracker.event(1, 305, 1))

    def test_single_button_cannot_count_as_both_sides(self):
        self.assertTrue(watcher.distinct_chord(MAPPING))
        self.assertFalse(watcher.distinct_chord([dict(name='hotkey', type='button', code=304, value=1),
                                                dict(name='start', type='button', code=304, value=1)]))
        self.assertFalse(watcher.distinct_chord([dict(name='hotkey', type='button', code=304, value=1),
                                                dict(name='start', type='button', code=304, value=0)]))

    def test_axis_only_hotkey_is_not_opened_as_a_pressed_control(self):
        axis_mapping=[dict(name='hotkey', type='axis', code=0, value=1),
                      dict(name='start', type='button', code=305, value=1)]
        source={'id':'source','mapping':axis_mapping}
        candidate={'id':'source','event':'/dev/input/event-test','joystick':'/dev/input/js-test','mapping':axis_mapping}
        opened={}
        with patch.object(watcher,'controller_candidates',return_value=[candidate]), \
             patch.object(watcher,'find_saved_controller',return_value=candidate), \
             patch.object(watcher,'session_mapping',return_value=axis_mapping), \
             patch.object(watcher,'translate_es_mapping',return_value=axis_mapping), \
             patch.object(watcher.os,'open',return_value=10) as open_call, \
             patch.object(watcher.os,'close') as close_call:
            watcher.open_saved_sources([source],Path('/es.xml'),opened)
        self.assertFalse(opened)
        self.assertEqual(open_call.call_count,1)
        close_call.assert_called_once_with(10)

    def test_opening_sources_is_read_only_and_nonexclusive(self):
        source={'id':'source','mapping':MAPPING}
        candidate={'id':'source','event':'/dev/input/event-test','joystick':'/dev/input/js-test','mapping':MAPPING}
        opened={}
        with patch.object(watcher,'controller_candidates',return_value=[candidate]), \
             patch.object(watcher,'find_saved_controller',return_value=candidate), \
             patch.object(watcher,'session_mapping',return_value=MAPPING), \
             patch.object(watcher,'translate_es_mapping',return_value=MAPPING), \
             patch.object(watcher,'input_axis_ranges',return_value={}), \
             patch.object(watcher.os,'open',side_effect=[10,11]) as open_call, \
             patch.object(watcher.os,'close') as close_call:
            watcher.open_saved_sources([source],Path('/es.xml'),opened)
        self.assertEqual(set(opened),{11})
        self.assertEqual(open_call.call_args_list[0][0][1],os.O_RDONLY | os.O_NONBLOCK)
        self.assertEqual(open_call.call_args_list[1][0][1],os.O_RDONLY | os.O_NONBLOCK)
        close_call.assert_called_once_with(10)


class WatcherLifecycleTests(unittest.TestCase):
    def test_ready_and_parent_eof_exit(self):
        with tempfile.TemporaryDirectory() as tmp:
            config=Path(tmp)/'config.json'
            saved={'id':'fixture','name':'fixture','mapping':MAPPING}
            config.write_text(json.dumps({'format':2,'platform':'retropie','players':[{'player':1,'sources':[saved]}],
                                          'virtualglove_player':None,'physical_scope':'nes'}))
            environment=dict(os.environ, PYTHONPATH=str(Path(watcher.__file__).resolve().parent.parent))
            proc=subprocess.Popen([sys.executable,'-u','-m','router_shared.passive_exit_watcher',
                                   '--config',str(config),'--es-inputs',str(Path(tmp)/'inputs.xml')],
                                  stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,env=environment)
            try:
                self.assertEqual(proc.stdout.readline(),b'READY\n')
                proc.stdin.close();self.assertEqual(proc.wait(timeout=4),0)
            finally:
                if proc.poll() is None: proc.kill();proc.wait()
                proc.stdout.close();proc.stderr.close()

    def test_no_player_one_source_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            config=Path(tmp)/'config.json'
            config.write_text(json.dumps({'format':2,'platform':'retropie','players':[],
                                          'virtualglove_player':None,'physical_scope':'nes'}))
            environment=dict(os.environ, PYTHONPATH=str(Path(watcher.__file__).resolve().parent.parent))
            proc=subprocess.run([sys.executable,'-m','router_shared.passive_exit_watcher',
                                 '--config',str(config),'--es-inputs',str(Path(tmp)/'es.xml')],
                                input=b'',stdout=subprocess.PIPE,stderr=subprocess.PIPE,env=environment,timeout=4)
            self.assertEqual(proc.returncode,1)
            self.assertNotIn(b'READY',proc.stdout)
            self.assertIn(b'No Player 1 physical sources',proc.stderr)
