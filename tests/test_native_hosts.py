import argparse, hashlib, json, os, pwd, tempfile, unittest
from pathlib import Path
from unittest.mock import patch
from router_shared import controller_router as router, retropie_native as native
from router_shared.launch_install import wrap_commands, install_retropie, register_native_host
from router_shared.native_sessions import running_native_session
from router_shared.systems import catalog

class NativeHostTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
    def test_script_argument_is_not_double_wrapped(self):
        ra='/opt/retropie/emulators/retroarch/bin/retroarch'
        text='adam = "bash /opt/adam/launch.sh '+ra+' -L core %ROM%"\n'
        self.assertEqual(wrap_commands(text,system='adam'),text)
        for prefix in ('','ENV=1 ','CON:','XINIT:'):
            text='core = "'+prefix+ra+' -L core %ROM%"\n';changed=wrap_commands(text,system='nes')
            self.assertIn('--system nes '+ra,changed);self.assertEqual(wrap_commands(changed,system='nes'),changed)
    def test_nested_ports_and_repeat_install_preserve_settings(self):
        configs=self.root/'configs';port=configs/'ports/doom';port.mkdir(parents=True)
        cfg=port/'emulators.cfg';cfg.write_text('default = "lr-prboom"\nlr-prboom = "/opt/retropie/emulators/retroarch/bin/retroarch -L prboom %ROM%"\n')
        saved=port/'retroarch.cfg';saved.write_text('input_driver = "custom"\n');before=saved.read_bytes();root=self.root/'installed'
        self.assertEqual(install_retropie(configs,root),[str(cfg)]);self.assertIn('--system ports ',cfg.read_text())
        self.assertEqual(install_retropie(configs,root),[]);self.assertEqual(saved.read_bytes(),before)
        self.assertTrue((root/'lib/router_shared/retropie_native.py').is_file());self.assertTrue((root/'bin/native-route').is_file())
    def test_catalog_requires_exact_native_registration(self):
        folder=self.root/'n64';folder.mkdir();cfg=folder/'emulators.cfg';command='python3 /installed/native-route --entry n64-a --rom %ROM%'
        cfg.write_text('default = "native"\nnative = "'+command+'"\n');provider=self.root/'host.py';provider.write_text('def native_session(root): return None,None\n')
        manifest=self.root/'adapters.json';register_native_host([{'path':str(provider)}],{str(cfg):{'system':'n64','kind':'native','command_sha256':[hashlib.sha256(command.encode()).hexdigest()]}},manifest)
        row=next(r for r in catalog('retropie',{},self.root,adapters=manifest)if r['id']=='n64');self.assertEqual(row['capability'],'native')
        cfg.write_text(cfg.read_text().replace('--entry n64-a','--entry unknown'));self.assertNotIn('n64',{r['id']for r in catalog('retropie',{},self.root,adapters=manifest)})
    def test_native_provider_blocks_save_and_rollback(self):
        provider=self.root/'host.py';provider.write_text('def native_session(root): return "qualified-native","n64"\n');manifest=self.root/'adapters.json';manifest.write_text(json.dumps({'schema':1,'providers':[{'path':str(provider)}]}))
        with patch('router_shared.native_sessions.ADAPTERS',manifest),patch.object(native,'native_session',return_value=(None,None)),patch.object(router,'retroarch_running',return_value=False):
            self.assertEqual(running_native_session(),('qualified-native','n64'));store=router.RouterStore(self.root/'router.json','retropie',self.root/'es.xml');self.assertTrue(store._managed_game_running())
            for op in ('save','rollback'):
                with self.assertRaisesRegex(ValueError,'Close'):store.operate(op,{'revision':store.read()['revision'],'config':{}})
    def test_disabled_scope_never_touches_devices(self):
        args=argparse.Namespace(entry='game',rom='/roms/Game name.7z',basename='Game name',xres='',yres='',test_seconds=0);entry={'system':'n64','command':'/bin/emulator %ROM%'}
        with patch.object(native.os,'geteuid',return_value=123),patch.object(native,'UID',123),patch.object(native,'registry',return_value={'game':entry}),patch('router_shared.native_sessions.launch_policy',return_value={'physical_scope':'nes'}),patch.object(native,'passthrough',return_value=17) as passthrough,patch.object(native,'inputs') as inputs,patch.object(native.subprocess,'run') as run:
            self.assertEqual(native.prepare(args),17)
        passthrough.assert_called_once_with(args,entry);inputs.assert_not_called();run.assert_not_called();self.assertEqual(native.expand_command(args,entry),"/bin/emulator '/roms/Game name.7z'")
    def test_worker_requires_registered_system_and_excludes_inspect(self):
        state=self.root/'state';run=state/'runs/abc';run.mkdir(parents=True);proc=self.root/'proc/123';proc.mkdir(parents=True);launcher='/opt/controller-router/bin/native-route'
        (proc/'cmdline').write_bytes(('python3\0'+launcher+'\0--worker\0'+str(run)+'\0').encode());(proc/'exe').symlink_to('/usr/bin/python3.7');registry=self.root/'registry.json';registry.write_text(json.dumps({'runtime':{'user':pwd.getpwuid(os.getuid()).pw_name,'state_root':str(state),'launcher':launcher},'entries':{'game':{'system':'n64'}}}))
        for inspect,system,expected in [(True,'n64',(None,None)),(False,'psp',(None,None)),(False,'n64',('native-merged','n64'))]:
            (run/'request.json').write_text(json.dumps({'entry':'game','system':system,'inspect':inspect}));self.assertEqual(native.native_session(proc.parent,registry),expected)
    def test_setup_native_wording_and_saved_selection_preservation(self):
        source=(Path(__file__).parents[1]/'uno_portal/python/setup.html').read_text();self.assertIn('All supported systems',source);self.assertIn('every game has been play-tested',source);self.assertIn("system.capability==='native'",source);self.assertIn('snapshot.config?.physical_systems',source)

    def test_daphne_preserves_player_buttons_and_exit_on_either_player(self):
        from router_shared.retropie_daphne import routed_buttons
        self.assertEqual(routed_buttons([({10},0,0),(set(),0,0)]),{4})
        self.assertEqual(routed_buttons([(set(),0,0),({10},0,0)]),{9})
        self.assertEqual(routed_buttons([({11},0,0),(set(),0,0)]),{3})
        for states in [ [({10,11},0,0),(set(),0,0)], [(set(),0,0),({10,11},0,0)], [({12,11},0,0),(set(),0,0)] ]:
            self.assertEqual(routed_buttons(states),{11})
        self.assertEqual(routed_buttons([({0},0,0),(set(),0,0)]),{0})

    def test_installed_host_interpretation_is_explicit_and_keeps_original_inputs(self):
        from router_shared.native_sessions import transform_controls
        provider=self.root/'host.py';provider.write_text("def transform_controls(buttons,axes,core,system):\n if core=='native' and axes.get('hat_x'):axes['lx']=32767\n return buttons,axes\n")
        manifest=self.root/'adapters.json';manifest.write_text(json.dumps({'schema':1,'providers':[{'path':str(provider)}]}))
        original={'hat_x':1};buttons={'a'}
        self.assertEqual(transform_controls(buttons,original,'native','n64',manifest),({'a'},{'hat_x':1,'lx':32767}))
        self.assertEqual(original,{'hat_x':1});self.assertEqual(buttons,{'a'})
        self.assertEqual(transform_controls(buttons,original,'libretro','nes',manifest),({'a'},{'hat_x':1}))

    def test_router_rescans_processes_only_when_they_change(self):
        proc=self.root/'proc';proc.mkdir();(proc/'100').mkdir();(proc/'self').mkdir()
        device=router.ControllerRouterDevice.__new__(router.ControllerRouterDevice)
        device.proc_root=proc;device.session_context=(None,None)
        device.session_checked_at=device.session_scanned_at=0.0;device.session_pids=None
        device.session_recheck=False
        step,full=router.SESSION_CHECK_SECONDS,router.SESSION_FULL_SCAN_SECONDS
        with patch.object(router,'running_game_session',return_value=(None,None)) as scan:
            device._game_session(100.0);self.assertEqual(scan.call_count,1)
            device._game_session(100.0+step);self.assertEqual(scan.call_count,2)  # follow-up after first scan
            device._game_session(100.0+1.5*step);device._game_session(100.0+2*step)
            self.assertEqual(scan.call_count,2)           # same processes: no rescan
            (proc/'200').mkdir()                          # launcher starts as a shell...
            device._game_session(100.0+3*step);self.assertEqual(scan.call_count,3)
            scan.return_value=('fceumm_libretro.so','nes')  # ...then execs into the emulator
            self.assertEqual(device._game_session(100.0+4*step),('fceumm_libretro.so','nes'))
            self.assertEqual(scan.call_count,4)           # follow-up check catches it
            device._game_session(100.0+5*step);self.assertEqual(scan.call_count,4)
            scan.return_value=('nestopia_libretro.so','nes')
            self.assertEqual(device._game_session(100.0+4*step+full),('nestopia_libretro.so','nes'))
            self.assertEqual(scan.call_count,5)           # periodic safety scan
            (proc/'200').rmdir();scan.return_value=(None,None)
            self.assertEqual(device._game_session(100.0+5*step+full),(None,None))
            self.assertEqual(scan.call_count,6)           # the game exited
        self.assertLessEqual(step,2.0);self.assertLessEqual(full,30.0)  # start/exit stay prompt
        self.assertEqual(router.process_ids(proc),frozenset({'100'}))
        self.assertIsNone(router.process_ids(self.root/'missing'))

    def test_input_signature_tracks_hotplug_replug_and_mapping_edits(self):
        sysfs=self.root/'sys';sysfs.mkdir();(sysfs/'event3').mkdir()
        es=self.root/'es_input.cfg';es.write_text('<inputList/>')
        with patch.dict(os.environ,{'CONTROLLER_ROUTER_SOURCES_FILE':''}):
            first=router.input_signature(sysfs,es)
            self.assertEqual(router.input_signature(sysfs,es),first)
            (sysfs/'event4').mkdir();plugged=router.input_signature(sysfs,es)
            self.assertNotEqual(plugged,first)                       # hotplug
            (sysfs/'event4').rmdir();(sysfs/'spare').mkdir();(sysfs/'spare').rename(sysfs/'event4')
            self.assertNotEqual(router.input_signature(sysfs,es),plugged)  # same name, new device
            before=router.input_signature(sysfs,es);es.write_text('<inputList><inputConfig/></inputList>')
            self.assertNotEqual(router.input_signature(sysfs,es),before)   # remapped in EmulationStation
        self.assertIsNone(router.input_signature(self.root/'missing',es))

    def test_discovery_and_index_checks_skip_unchanged_inputs(self):
        device=router.ControllerRouterDevice.__new__(router.ControllerRouterDevice)
        device.sys_root=self.root;device.es_inputs=self.root/'es_input.cfg'
        for purpose in ('discovery','index'):
            setattr(device,purpose+'_signature',None);setattr(device,purpose+'_refreshed_at',0.0)
        device.discovery_forced=device.discovery_recheck=device.index_recheck=False
        full=router.INPUT_FULL_REFRESH_SECONDS
        with patch.object(router,'input_signature',return_value=('same',)) as signature:
            self.assertTrue(device._input_changed('discovery',100.0))          # first check
            self.assertTrue(device._input_changed('discovery',101.0))          # follow-up check
            self.assertFalse(device._input_changed('discovery',102.0))         # nothing changed
            self.assertTrue(device._input_changed('index',101.0))              # independent schedule
            self.assertTrue(device._input_changed('index',102.0))
            self.assertFalse(device._input_changed('index',103.0))
            device.discovery_forced=True
            self.assertTrue(device._input_changed('discovery',103.0))          # controller disconnected
            self.assertFalse(device.discovery_forced)
            self.assertFalse(device._input_changed('discovery',104.0))
            signature.return_value=('changed',)
            self.assertTrue(device._input_changed('discovery',104.5))          # device plugged in
            self.assertTrue(device._input_changed('discovery',105.5))          # once more while it settles
            self.assertFalse(device._input_changed('discovery',106.5))
            self.assertTrue(device._input_changed('index',104.5))
            self.assertTrue(device._input_changed('discovery',105.5+full))     # periodic full refresh
            signature.return_value=None
            self.assertTrue(device._input_changed('discovery',105.6+full))     # unreadable: always refresh
        self.assertLessEqual(full,30.0)

    def test_every_installed_provider_stays_loaded(self):
        from router_shared import native_sessions
        paths=[]
        for name in ('first','second','third'):
            path=self.root/(name+'-host.py');path.write_text('LOADS=globals().get("LOADS",0)+1\nNAME=%r\n'%name);paths.append(path)
        modules=[native_sessions.load_provider(path) for path in paths]
        self.assertEqual([native_sessions.load_provider(path) for path in paths],modules)  # no re-import
        self.assertEqual([module.NAME for module in modules],['first','second','third'])
        os.utime(paths[0],ns=(1,1))
        self.assertIsNot(native_sessions.load_provider(paths[0]),modules[0])  # edited file reloads
        self.assertIs(native_sessions.load_provider(paths[1]),modules[1])

    def test_native_game_blocks_output_recreation_on_service_restart(self):
        config={'platform':'retropie','players':[],'virtualglove_player':None}
        with patch.object(router,'load_config',return_value=config),patch.object(router,'running_game_session',return_value=('native-merged','n64')),patch.object(router,'UInputMergedGamepad') as sink:
            with self.assertRaisesRegex(RuntimeError,'restarted during play'):
                router.ControllerRouterDevice(self.root/'router.json',self.root/'retroarch.cfg')
            sink.assert_not_called()
