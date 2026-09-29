import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from router_shared import controller_router as router, launch
from router_shared.systems import policy, catalog, argument_system
from router_shared.launch_install import wrap_commands, patch_batocera_generator

class SystemsTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
    def test_policy_legacy_and_validation(self):
        self.assertEqual(policy({}),('all',[]))
        self.assertEqual(policy({'physical_scope':'systems','physical_systems':['genesis','nes','megadrive']}),('systems',['megadrive','nes']))
        for values in ('nes', ['../nes'], [1]):
            with self.assertRaises(ValueError):policy({'physical_scope':'systems','physical_systems':values})
    def test_same_core_different_systems(self):
        config={'physical_scope':'systems','physical_systems':['megadrive']}
        self.assertTrue(router.routes_physical_core(config,'genesis_plus_gx_libretro.so','megadrive'))
        self.assertFalse(router.routes_physical_core(config,'genesis_plus_gx_libretro.so','mastersystem'))
        self.assertFalse(router.routes_physical_core(config,'genesis_plus_gx_libretro.so'))
        self.assertFalse(router.routes_physical_core(config,'fceumm_libretro.so','nes'))
    def test_installed_catalog_and_retained_missing_selection(self):
        for system in ('nes','megadrive','psp'):
            p=self.root/system;p.mkdir();(p/'emulators.cfg').write_text('core = "/opt/retropie/emulators/retroarch/bin/retroarch -L core %ROM%"')
        rows=catalog('retropie',{'physical_scope':'systems','physical_systems':['nes','snes']},self.root)
        self.assertEqual({row['id'] for row in rows},{'nes','megadrive','psp','snes'})
        self.assertEqual(next(row['name'] for row in rows if row['id']=='megadrive'),'Mega Drive / Genesis')
        self.assertFalse(next(row['enabled'] for row in rows if row['id']=='psp'))
    def test_new_default_and_old_client_preserves_scope(self):
        p=self.root/'config.json';store=router.RouterStore(p,'retropie',self.root/'es.xml',activity_check=lambda:False)
        self.assertEqual(store.read()['config']['physical_scope'],'nes')
        current={'format':2,'platform':'retropie','players':[],'virtualglove_player':None,'physical_scope':'systems','physical_systems':['megadrive']}
        p.write_text(json.dumps(current))
        with patch.object(router,'controller_candidates',return_value=[]):
            saved=store.operate('save',{'revision':store.read()['revision'],'config':{'players':[],'virtualglove_player':None}})
        self.assertEqual(saved['config'],current)
        with patch.object(router,'controller_candidates',return_value=[]):
            changed=store.operate('save',{'revision':saved['revision'],'config':{'players':[],'virtualglove_player':None,'physical_scope':'systems','physical_systems':['nes']}})
        self.assertEqual(changed['config']['physical_systems'],['nes'])
        restored=store.operate('rollback',{'revision':changed['revision']})
        self.assertEqual(restored['config'],current)
    def test_native_default_excluded_even_with_libretro_alternative(self):
        p=self.root/'amiga';p.mkdir()
        (p/'emulators.cfg').write_text('default = "amiberry"\namiberry = "/opt/amiberry %ROM%"\nlr-puae = "/opt/retroarch -L puae %ROM%"\n')
        config={'physical_scope':'systems','physical_systems':['amiga']}
        self.assertNotIn('amiga',{row['id'] for row in catalog('retropie',config,self.root)})
        (p/'emulators.cfg').write_text('default = "lr-puae"\nlr-puae = "/opt/retroarch -L puae %ROM%"\n')
        self.assertIn('amiga',{row['id'] for row in catalog('retropie',config,self.root)})
    def test_batocera_native_only_excluded(self):
        p=self.root/'systems.xml'
        p.write_text('<systemList><system><name>amiga</name><emulators><emulator name="amiberry"/></emulators></system><system><name>psp</name><emulators><emulator name="libretro"/></emulators></system></systemList>')
        rows=catalog('batocera',{'physical_scope':'all'},p)
        self.assertIn('psp',{row['id'] for row in rows})
        self.assertNotIn('amiga',{row['id'] for row in rows})
    def test_retroarch_identity_from_environment(self):
        p=self.root/'123';p.mkdir();(p/'cmdline').write_bytes(b'/usr/bin/retroarch\0-L\0/core/genesis_plus_gx_libretro.so\0');(p/'environ').write_bytes(b'CONTROLLER_ROUTER_SYSTEM=mastersystem\0')
        self.assertEqual(router.running_retroarch_session(self.root),('genesis_plus_gx_libretro.so','mastersystem'))
    def test_passthrough_preserves_every_argument_and_no_prepare(self):
        p=self.root/'config';p.write_text('{}');args=['-L','/core/genesis_plus_gx_libretro.so','--appendconfig','cabinet.cfg','game.7z']
        with patch.object(launch.sys,'argv',['adapter','--config',str(p),'--system','megadrive','--retroarch','/test/retroarch','--']+args),patch.object(router,'load_config',return_value={'physical_scope':'systems','physical_systems':['nes']}),patch.object(launch.os,'execv',side_effect=SystemExit(0)) as execute,patch.object(launch,'prepare') as prepare,patch.dict(launch.os.environ,{},clear=True):
            with self.assertRaises(SystemExit):launch.main()
            self.assertEqual(launch.os.environ['CONTROLLER_ROUTER_SYSTEM'],'megadrive')
        execute.assert_called_once_with('/test/retroarch',['/test/retroarch']+args);prepare.assert_not_called()
    def test_wrapper_identity_repeatable(self):
        text='core = "/opt/retropie/emulators/retroarch/bin/retroarch -L core %ROM%"'
        updated=wrap_commands(text,system='megadrive');self.assertIn('--system megadrive',updated)
        self.assertEqual(wrap_commands(updated,system='megadrive'),updated)
        legacy=wrap_commands(text);self.assertEqual(wrap_commands(legacy,system='megadrive'),updated)
        self.assertEqual(argument_system(['--config','/opt/retropie/configs/megadrive/retroarch.cfg']),'megadrive')
    def test_block_scope_change_during_unmanaged_game(self):
        store=router.RouterStore(self.root/'config','retropie',self.root/'es.xml')
        with patch.object(router,'running_retroarch_core',return_value='ppsspp_libretro.so'):
            with self.assertRaisesRegex(ValueError,'Close'):store.operate('save',{'revision':store.read()['revision'],'config':{}})
