import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from router_shared import launch
from router_shared.launch_install import wrap_commands, repair_profiles

class LaunchTests(unittest.TestCase):
    def test_retired_merged_commands_cannot_write_saved_config(self):
        from router_shared import merged_gamepad
        self.assertFalse(hasattr(merged_gamepad, 'install_retroarch_assignment'))
        self.assertFalse(hasattr(merged_gamepad, 'MergedGamepadDevice'))
        with self.assertRaisesRegex(SystemExit, 'serve and sync-index commands are retired'):
            merged_gamepad.main()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
    def device(self, event, name='VirtualGlove Merged Player 1', product='5651'):
        folder = self.root / event / 'device'
        (folder / 'id').mkdir(parents=True)
        (folder / 'name').write_text(name)
        (folder / 'id/vendor').write_text('1209')
        (folder / 'id/product').write_text(product)
    def test_scope_matches_service_and_adapter_including_buddy_wrappers(self):
        from router_shared.controller_router import routes_physical_core
        for core in ('fceumm_libretro.so', 'nestopia_libretro.so',
                     'nestopia_powerglove_libretro.so', 'rob_vision_fceumm_libretro.so',
                     'rob_vision_nestopia_libretro.so', 'robvision_nestopia_libretro.so'):
            self.assertTrue(routes_physical_core({'physical_scope':'nes'}, core))
        for core in ('ppsspp_libretro.so', 'mednafen_pce_libretro.so'):
            self.assertFalse(routes_physical_core({'physical_scope':'nes'}, core))
            self.assertTrue(routes_physical_core({'physical_scope':'all'}, core))
        self.assertFalse(routes_physical_core({'physical_scope':'all'}, None))
        self.assertEqual(launch.launch_core(['--libretro=/cores/rob_vision_nestopia_libretro.so']),
                         'rob_vision_nestopia_libretro.so')
        self.assertEqual(launch.launch_core(['-L','/cores/fceumm_libretro.so']), 'fceumm_libretro.so')

    def test_nes_scope_preserves_other_system_launch_without_preparing(self):
        config = self.root / 'router.json'; config.write_text('{}')
        arguments = ['-L', '/cores/ppsspp_libretro.so', '--appendconfig', 'frontend.cfg', 'game.iso']
        with patch.object(launch.sys, 'argv', ['adapter', '--config', str(config),
                          '--retroarch', '/test/retroarch', '--'] + arguments), \
             patch('router_shared.controller_router.load_config', return_value={'physical_scope':'nes'}), \
             patch.object(launch.os, 'execv', side_effect=SystemExit(0)) as execute, \
             patch.object(launch, 'prepare') as prepare:
            with self.assertRaises(SystemExit):
                launch.main()
        execute.assert_called_once_with('/test/retroarch', ['/test/retroarch'] + arguments)
        prepare.assert_not_called()

    def test_nes_assignment_guard_includes_buddy_core(self):
        from router_shared import controller_router as router
        config=self.root/'router.json';config.write_text('{}')
        store=router.RouterStore(config,'retropie',self.root/'es.xml')
        with patch.object(router,'load_config',return_value={'physical_scope':'nes'}), \
             patch.object(router,'running_retroarch_core',return_value='rob_vision_nestopia_libretro.so'):
            self.assertTrue(store._managed_game_running())

    def test_identity_and_actual_slot(self):
        self.device('event1', 'Other pad')
        self.device('event8')
        self.assertEqual(launch.resolve([1], self.root, ['/dev/input/event1', '/dev/input/event8'])[1]['slot'], 1)
    def test_wrong_product_is_missing(self):
        self.device('event1', product='0001')
        self.assertEqual(launch.resolve([1], self.root, ['/dev/input/event1']), {})
    def test_duplicate_stops_launch(self):
        self.device('event1'); self.device('event2')
        with self.assertRaisesRegex(RuntimeError, 'Duplicate'):
            launch.resolve([1], self.root, ['/dev/input/event1', '/dev/input/event2'])
    def test_append_precedence_preserves_args(self):
        result = launch.append_settings(['-L','core.so','--appendconfig','first|second','--config','saved.cfg','rom.nes'], 'session.cfg')
        self.assertEqual(result, ['-L','core.so','--config','saved.cfg','rom.nes','--appendconfig','first|second|session.cfg'])
    def test_wrap_repeat_preserves_environment_and_overrides(self):
        text = 'lr-test = "ENV=1 /opt/retropie/emulators/retroarch/bin/retroarch --appendconfig other %ROM%"\n'
        result = wrap_commands(text)
        self.assertEqual(wrap_commands(result), result)
        self.assertIn('ENV=1 /opt/controller-router/bin/retroarch-route ', result)
        self.assertIn('--appendconfig other %ROM%', result)
    def test_missing_does_not_write_settings(self):
        output=self.root/'session.cfg'
        config={'players':[], 'virtualglove_player':1}
        with self.assertRaisesRegex(RuntimeError,'missing'):
            launch.prepare(config, Path('/missing'), output, wait_seconds=0, resolver=lambda players: {})
        self.assertFalse(output.exists())
    def test_native_and_legacy_settings(self):
        config={'players':[], 'virtualglove_player':1}
        output=self.root/'session.cfg'
        identity={1:{'player':1,'name':'VirtualGlove Merged Player 1','slot':4}}
        for mode in ('legacy-udev','native-reservations'):
            with patch.object(launch,'compatibility',return_value=mode):
                result=launch.prepare(config, Path('/fake'), output, resolver=lambda players:identity)
            self.assertEqual(result['mode'],mode)
            self.assertIn('joypad_index = "4"',output.read_text())
            self.assertEqual('device_reservation_type = "2"' in output.read_text(),mode=='native-reservations')
            if mode == 'native-reservations':
                import re
                indexes = re.findall(r'input_player\d+_joypad_index = "(\d+)"', output.read_text())
                self.assertEqual(sorted(map(int,indexes)), list(range(16)))
            self.assertNotIn('input_exit_emulator',output.read_text())
    def test_profiles_repair_identity_preserve_extra_hotkeys(self):
        owned=self.root/'VirtualGlove Merged Player 1.cfg'
        owned.write_text('input_device = "Wrong"\ninput_exit_emulator_btn = "14"\n')
        other=self.root/'Other.cfg'; other.write_text('untouched')
        repair_profiles(self.root)
        self.assertIn('input_device = "VirtualGlove Merged Player 1"',owned.read_text())
        self.assertIn('input_exit_emulator_btn = "14"',owned.read_text())
        self.assertEqual(other.read_text(),'untouched')
        self.assertEqual(owned.with_name(owned.name+'.before-router-session-routing').read_text(),'input_device = "Wrong"\ninput_exit_emulator_btn = "14"\n')
    def test_unknown_build_falls_back(self):
        with patch.object(launch.subprocess,'run',return_value=type('Result',(),{'returncode':0,'stdout':'Custom RetroArch build'})()):
            self.assertEqual(launch.compatibility(Path('/not-read')), 'legacy-udev')
        with patch.object(launch.subprocess, 'run', side_effect=launch.subprocess.TimeoutExpired('retroarch', 5)):
            self.assertEqual(launch.compatibility(Path('/not-read')), 'legacy-udev')
    def test_child_lifetime_sets_linux_parent_death_signal(self):
        from unittest.mock import Mock
        libc = Mock(); libc.prctl.return_value = 0
        with patch.object(launch.ctypes, 'CDLL', return_value=libc), patch.object(launch.os, 'getppid', return_value=7):
            launch._terminate_with_adapter()
        libc.prctl.assert_called_once_with(1, launch.signal.SIGTERM, 0, 0, 0)
    def test_batocera_generator_wrap_is_repeatable_and_preserves_other_code(self):
        from router_shared.launch_install import patch_batocera_generator
        original='class Generator:\n    def generate(self):\n        other_setting = 7\n        return Command.Command(array=commandArray, env={"XDG_CONFIG_HOME":CONFIGS})\n'
        patched=patch_batocera_generator(original, '/userdata/router/adapter')
        self.assertEqual(patch_batocera_generator(patched, '/userdata/router/adapter'), patched)
        self.assertIn('other_setting = 7', patched)
        self.assertLess(patched.index('session adapter'),patched.index('return Command'))
        with self.assertRaisesRegex(RuntimeError,'Unsupported'):
            patch_batocera_generator('changed upstream format', '/adapter')
    def test_version_and_feature_detection_both_required(self):
        binary=self.root/'retroarch';binary.write_bytes(b'reserved_device device_reservation_type')
        with patch.object(launch.subprocess,'run',return_value=type('Result',(),{'returncode':0,'stdout':'RetroArch - Frontend\nVersion: 1.20.0'})()):
            self.assertEqual(launch.compatibility(binary),'native-reservations')
            binary.write_bytes(b'no reservation support')
            self.assertEqual(launch.compatibility(binary),'legacy-udev')
    def test_repeat_install_preserves_saved_configs_and_native_arguments(self):
        from router_shared.launch_install import install_retropie
        configs=self.root/'configs';(configs/'nes').mkdir(parents=True)
        saved=configs/'nes/retroarch.cfg';saved.write_text('input_player1_joypad_index = "5"\n')
        emulators=configs/'nes/emulators.cfg'
        emulators.write_text('native = "ENV=1 /opt/retropie/emulators/retroarch/bin/retroarch --device=1:517 --appendconfig native.cfg %ROM%"\n')
        original=saved.read_bytes();native=emulators.read_bytes()
        first=install_retropie(configs,self.root/'installed')
        self.assertEqual(len(first),1)
        second=install_retropie(configs,self.root/'installed')
        self.assertEqual(second,[])
        self.assertEqual(saved.read_bytes(),original)
        self.assertEqual(emulators.with_name(emulators.name+'.before-router-session-routing').read_bytes(),native)
        self.assertIn('--device=1:517 --appendconfig native.cfg',emulators.read_text())
    def test_retire_only_router_owned_core_indexes(self):
        from router_shared.launch_install import retire_core_indexes, migrate_core_overrides
        text = 'video_shader_enable = "true"\ninput_player3_joypad_index = "9"\n# VirtualGlove Controller Router\ninput_player1_joypad_index = "2"\ninput_player1_start_btn = "11"\ninput_enable_hotkey_btn = "12"\n# End VirtualGlove Controller Router\n'
        expected = text.replace('input_player1_joypad_index = "2"\n', '')
        self.assertEqual(retire_core_indexes(text), expected)
        self.assertEqual(retire_core_indexes(expected), expected)
        self.assertEqual(retire_core_indexes('input_player1_joypad_index = "2"\n'), 'input_player1_joypad_index = "2"\n')
        path = self.root / 'all/retroarch/config/FCEUmm/FCEUmm.cfg'
        path.parent.mkdir(parents=True);path.write_text(text)
        self.assertEqual(migrate_core_overrides(self.root), [str(path)])
        self.assertEqual(path.read_text(), expected)
        self.assertEqual(path.with_name(path.name + '.before-router-session-routing').read_text(), text)
        self.assertEqual(migrate_core_overrides(self.root), [])

    def test_assignment_reload_keeps_output_objects(self):
        from router_shared.controller_router import ControllerRouterDevice, PlayerState
        from unittest.mock import Mock
        device=ControllerRouterDevice.__new__(ControllerRouterDevice)
        device.config={'players':[{'player':1,'sources':[{}]},{'player':2,'sources':[{}]}],'virtualglove_player':None}
        device.config_revision='old'
        device.players={p:PlayerState(p) for p in (1,2)}
        device.sinks={p:Mock() for p in (1,2)}
        original=dict(device.sinks)
        device.descriptors={}
        device._install_indexes=Mock()
        updated={'players':[{'player':2,'sources':[{}]}],'virtualglove_player':None}
        with patch('router_shared.controller_router.UInputMergedGamepad') as factory:
            device._reload_config(updated)
        factory.assert_not_called()
        self.assertEqual(device.sinks,original)
        for sink in device.sinks.values():sink.close.assert_not_called()
        self.assertEqual(list(device.players),[2])
    def test_shared_output_owner_excludes_concurrent_start(self):
        import os
        from router_shared.controller_router import acquire_output_owner
        path=self.root/'owner.lock'
        first=acquire_output_owner(path)
        try:
            with self.assertRaisesRegex(RuntimeError,'already owns'):
                acquire_output_owner(path)
        finally:
            os.close(first)
        second=acquire_output_owner(path)
        os.close(second)
    def test_repeat_install_repairs_root_config_owner_without_rewrite(self):
        from router_shared import launch_install
        from unittest.mock import MagicMock
        path=MagicMock();path.__str__.return_value='/opt/retropie/configs/nes/emulators.cfg'
        path.is_file.return_value=True;path.read_text.return_value='unchanged'
        path.stat.return_value=type('Stat',(),{'st_uid':0,'st_gid':0})()
        account=type('Account',(),{'pw_uid':1000,'pw_gid':1000})()
        with patch.object(launch_install.os,'geteuid',return_value=0), patch.object(launch_install.pwd,'getpwnam',return_value=account), patch.object(launch_install.os,'chown') as owner, patch.object(launch_install,'atomic_write') as writer:
            self.assertFalse(launch_install.replace_owned(path,'unchanged'))
        owner.assert_called_once_with(path,1000,1000)
        writer.assert_not_called()
