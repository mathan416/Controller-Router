"""Verify firmware boot artwork and the host's readiness acknowledgement."""
import io
import shutil
import subprocess
import tempfile
import unittest
from contextlib import nullcontext
from pathlib import Path
from unittest.mock import patch

from uno_portal.host.display_runtime import MatrixScheduler
from uno_portal.host.concurrent import ConcurrentLauncher


class StartupTests(unittest.TestCase):
    def test_acknowledgement_retries_until_delivered(self):
        scheduler = MatrixScheduler(send=lambda rows: True)
        with patch('uno_portal.host.display_runtime.TOKEN') as token, patch('uno_portal.host.display_runtime.urlopen') as request:
            token.read_text.return_value = 'test-only-token'
            response = io.BytesIO(b'{"delivered":true}')
            response.status = 200
            request.side_effect = [OSError('starting'), nullcontext(response)]
            self.assertFalse(scheduler.finish_startup())
            self.assertTrue(scheduler.finish_startup())
            self.assertTrue(scheduler.finish_startup())
            self.assertEqual(request.call_count, 2)
            self.assertEqual(request.call_args.args[0].full_url, 'http://127.0.0.1:8123/ready')
            self.assertEqual(request.call_args.args[0].data, b'{}')

    def test_hourglass_waits_for_every_installed_product(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            launcher = object.__new__(ConcurrentLauncher)
            launcher.apps = {name: {'path': root / name} for name in ('virtualglove', 'rob_vision')}
            for app in launcher.apps.values():
                app['path'].mkdir()
                (app['path'] / 'app.yaml').touch()
            launcher.selected = None
            launcher.game_owned = False
            with patch.object(launcher, '_health', side_effect=[(True, False), (False, False)]), patch.object(launcher, 'matrix', create=True) as matrix:
                launcher._reconcile_games()
                matrix.finish_startup.assert_not_called()
            with patch.object(launcher, '_health', return_value=(True, False)), patch.object(launcher, 'matrix', create=True) as matrix:
                launcher._reconcile_games()
                matrix.finish_startup.assert_called_once()

    @unittest.skipUnless(shutil.which('c++'), 'C++ compiler required for firmware harness')
    def test_firmware_loading_idle_and_product_frame_priority(self):
        sketch = Path(__file__).resolve().parents[1] / 'uno_portal/app/sketch/sketch.ino'
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'zephyr').mkdir()
            (root / 'Arduino_RouterBridge.h').write_text('''#include <string>
using String = std::string;
inline unsigned long nowMs = 10;
inline unsigned long millis() { return nowMs; }
inline void delay(int) {}
struct BridgeStub { void begin() {} template<class T> void provide(const char*, T) {} };
inline BridgeStub Bridge;
''')
            (root / 'Arduino_LED_Matrix.h').write_text('''#include <array>
#include <cstdint>
inline std::array<uint8_t, 104> drawn;
struct Arduino_LED_Matrix { void begin() {} void setGrayscaleBits(int) {} void draw(uint8_t* p) { for(int i=0;i<104;i++) drawn[i]=p[i]; } };
''')
            (root / 'zephyr/kernel.h').write_text('''struct k_thread {};
using k_thread_stack_t = int;
using k_tid_t = void*;
#define K_NO_WAIT 0
inline int* k_thread_stack_alloc(int, int) { return nullptr; }
inline void* k_thread_create(k_thread*, int*, int, void(*)(void*,void*,void*),void*,void*,void*,int,int,int) { return nullptr; }
inline void k_thread_name_set(void*, const char*) {}
inline void k_msleep(int) {}
''')
            harness = root / 'test.cpp'
            harness.write_text('#include <cassert>\n#include "' + str(sketch) + '''"
int main() {
  setup();
  assert(!startupComplete);
  auto initial = drawn;
  nowMs = 400; refreshDisplay();
  assert(drawn != initial);
  assert(!draw_router_frame("invalid"));
  assert(!startupComplete);
  assert(finish_router_startup());
  refreshDisplay();
  auto idle = drawn;
  assert(idle != initial);
  assert(draw_router_frame(String(104, '7')));
  nowMs += 100; refreshDisplay();
  for(auto pixel : drawn) assert(pixel == 7);
  nowMs += 2000; refreshDisplay();
  assert(drawn != std::array<uint8_t,104>{});
  assert(drawn != initial);
  for(auto pixel : drawn) assert(pixel <= 7);
}
'''.replace('  assert(drawn != std::array<uint8_t,104>{});\n', ''))
            subprocess.run(['c++', '-std=c++17', '-I', str(root), str(harness), '-o', str(root / 'test')], check=True, capture_output=True)
            subprocess.run([str(root / 'test')], check=True, capture_output=True)
