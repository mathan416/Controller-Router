"""Bounded core boot checks. Uses console ROMs only; never bundles their contents."""
import json
import os
import shlex
import subprocess
import tempfile
from pathlib import Path
root=Path('/home/pi/controller-router-session-test')
cases=[('gyromite','nes','lr-robvision-fceumm','Gyromite (World).7z'),
       ('stackup','nes','lr-robvision-nestopia','Stack-Up (World).7z'),
       ('super-glove-ball','nes','lr-nestopia-powerglove','Super Glove Ball (USA).7z'),
       ('ordinary-nes','nes','lr-fceumm','Gyruss (USA).7z'),
       ('psp','psp','lr-ppsspp','Bust A Move Deluxe PSP.cso')]
settings=root/'smoke.cfg'
settings.write_text('video_driver = "null"\naudio_driver = "null"\ngamemode_enable = "false"\nconfig_save_on_exit = "false"\npause_nonactive = "false"\nsavestate_auto_load = "false"\nsavestate_auto_save = "false"\n')
results=[]
for name,system,emulator,filename in cases:
 cfg=Path('/opt/retropie/configs')/system/'emulators.cfg'
 lines=cfg.read_text().splitlines()
 value=next(line.split('=',1)[1].strip()[1:-1] for line in lines if line.split('=',1)[0].strip()==emulator)
 rom=Path('/home/pi/RetroPie/roms')/system/filename
 with tempfile.TemporaryDirectory(prefix='router-rom-test-',dir=str(root)) as directory:
  if system=='nes':
   extracted=Path(directory)/(rom.stem+'.nes')
   extracted.write_bytes(subprocess.check_output(['7z','x','-so',str(rom)],stderr=subprocess.DEVNULL))
   assert extracted.read_bytes()[:4]==b'NES\x1a'
   content=extracted
  else:content=rom
  args=[str(content) if arg=='%ROM%' else arg for arg in shlex.split(value)]
  env=os.environ.copy()
  while args and '=' in args[0] and not args[0].startswith('/'):
   key,val=args.pop(0).split('=',1);env[key]=val
  args+=['--appendconfig',str(settings),'--max-frames','180','--verbose']
  log=root/(name+'-smoke.log')
  with log.open('w') as output:
   result=subprocess.run(['dbus-run-session','--']+args,env=env,stdout=output,stderr=output,timeout=35)
  text=log.read_text()
  assert result.returncode==0,(name,result.returncode)
  assert '"mode": "legacy-udev"' in text,(name,'missing routing diagnostics')
  assert '[Core]' in text,(name,'missing core boot')
  results.append({'game':name,'emulator':emulator,'exit':result.returncode,'routed':True,'log':str(log)})
print(json.dumps(results,indent=2))
