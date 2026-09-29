"""Root-only isolated live test. Never changes saved assignments or game configs."""
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from evdev import UInput, ecodes
from router_shared.controller_router import ControllerRouterDevice, _saved_source
from router_shared.merged_gamepad import UInputMergedGamepad, controller_candidates, BUTTON_CODES, CANONICAL_BUTTON_INDEX
from router_shared.launch import resolve

root=Path(sys.argv[1]); executable=Path(sys.argv[2])
root.mkdir(parents=True, exist_ok=True); root.chmod(0o755)
descriptor=root/'test-sources.json'
descriptor.write_text(json.dumps({'schema':1,'sources':[
 {'name':'Router Test Source %d'%p,'vendor':'1209','product':'%04x'%(0x6000+p),
  'mapping':[{'name':name,'type':'button','code':CANONICAL_BUTTON_INDEX[name],
              'value':1,'evdev_code':BUTTON_CODES[name]} for name in ('a','b','start','hotkey')]}
 for p in (1,2)]}))
os.environ['CONTROLLER_ROUTER_SOURCES_FILE']=str(descriptor)
router=None; process=None; sources={}; log=None; keyboard=None
subprocess.run(['systemctl','stop','virtualglove-controller-router'],check=True)
try:
 keyboard=UInput({ecodes.EV_KEY:list(range(1,128))},name='Router Keyboard Fixture')
 for p in (1,2):sources[p]=UInputMergedGamepad(name='Router Test Source %d'%p,product=0x6000+p)
 time.sleep(1)
 candidates=controller_candidates(root/'no-es.xml',source_file=descriptor)
 config={'format':2,'platform':'retropie','physical_scope':'all','virtualglove_player':None,
         'players':[{'player':p,'sources':[_saved_source(next(c for c in candidates if c['name']=='Router Test Source %d'%p))]} for p in (1,2)]}
 path=root/'router-test.json';path.write_text(json.dumps(config));path.chmod(0o644)
 router=ControllerRouterDevice(path,root/'unused-retroarch.cfg',root/'test.sock',es_inputs=root/'no-es.xml')
 before=resolve([1,2]); before_paths={p:str((Path('/sys/class/input')/Path(item['event']).name/'device').resolve()) for p,item in before.items()}
 runtime=root/'trace.cfg';runtime.write_text('pause_nonactive = "false"\nmenu_pause_libretro = "false"\njoypad_autoconfig_dir = "/opt/retropie/configs/all/retroarch/autoconfig"\ngamemode_enable = "false"\nvideo_driver = "null"\naudio_driver = "null"\ninput_driver = "udev"\nconfig_save_on_exit = "false"\ninput_exit_emulator_btn = "11"\ninput_enable_hotkey_btn = "12"\n')
 log_path=root/(executable.parent.name+'-trace.log');log=log_path.open('w')
 process=subprocess.Popen(['dbus-run-session','--','/opt/controller-router/bin/retroarch-route',str(executable),'--config',str(runtime),'-L',str(root.parent/'router_input_trace_libretro.so'),'--verbose'],stdout=log,stderr=log,start_new_session=True)
 deadline=time.monotonic()+15
 while 'ROUTER_TRACE frame=0' not in log_path.read_text() or not all(state.active for state in router.players.values()):
  if process.poll() is not None or time.monotonic()>deadline:raise RuntimeError('RetroArch input trace did not become ready')
  time.sleep(.1)
 time.sleep(1)
 if sys.argv[3:] == ['fault']:
  router.close();router=None
  subprocess.run(['systemctl','start','--no-block','virtualglove-controller-router'],check=True)
  time.sleep(1)
  assert resolve([1,2])=={}, 'Router rebuilt outputs during a running game'
  assert 'outputs were lost' in log_path.read_text(), 'Missing relaunch diagnostic'
  os.killpg(process.pid,signal.SIGTERM)
  try:process.wait(timeout=3)
  except subprocess.TimeoutExpired:os.killpg(process.pid,signal.SIGKILL);process.wait(timeout=3)
  print(json.dumps({'service_loss':'reported','midgame_rebuild':'blocked','relaunch_required':True}))
  sys.exit(0)
 keyboard.write(ecodes.EV_KEY,ecodes.KEY_ENTER,1);keyboard.syn();time.sleep(.3)
 keyboard.write(ecodes.EV_KEY,ecodes.KEY_ENTER,0);keyboard.syn();time.sleep(.3)
 sources[1].write({'a'},{});time.sleep(.4);sources[1].write(set(),{})
 sources[2].write({'b'},{});time.sleep(.4);sources[2].write(set(),{})
 # Sleep and wake BOTH sources in reverse order. Merged output objects survive.
 for source in sources.values():source.close()
 time.sleep(1.5)
 for p in (2,1):sources[p]=UInputMergedGamepad(name='Router Test Source %d'%p,product=0x6000+p)
 time.sleep(2)
 sources[1].write({'b'},{});time.sleep(.4);sources[1].write(set(),{})
 sources[2].write({'a'},{});time.sleep(.4);sources[2].write(set(),{})
 after=resolve([1,2]);after_paths={p:str((Path('/sys/class/input')/Path(item['event']).name/'device').resolve()) for p,item in after.items()}
 assert before_paths==after_paths,(before_paths,after_paths)
 sources[1].write({'hotkey'},{});time.sleep(.3)
 print('hotkey_state',router.players[1].desired()[0],flush=True)
 sources[1].write({'hotkey','start'},{});time.sleep(.3)
 if process.poll() is None:
  sources[1].write({'hotkey'},{});time.sleep(.3)
  sources[1].write({'hotkey','start'},{});
 process.wait(timeout=5)
 print('trace_exit_status',process.returncode,flush=True)
 text=log_path.read_text()
 for expected in ('player=1 mask=8','player=1 mask=256','player=2 mask=1','player=1 mask=1','player=2 mask=256'):
  assert expected in text, 'Missing '+expected
 assert 'outputs were lost' not in text
 print(json.dumps({'retroarch':str(executable),'stable_outputs':before_paths,'port_reads_before_after_hotplug':'passed','exit_hotkey':'passed','keyboard_start':'passed','log':str(log_path)}))
finally:
 if process and process.poll() is None:
  os.killpg(process.pid,signal.SIGTERM)
  try:process.wait(timeout=3)
  except subprocess.TimeoutExpired:os.killpg(process.pid,signal.SIGKILL);process.wait(timeout=3)
 if log:log.close()
 if router:router.close()
 for source in sources.values():source.close()
 if keyboard:keyboard.close()
 subprocess.run(['systemctl','start','virtualglove-controller-router'],check=True)
