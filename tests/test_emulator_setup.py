import hashlib
import json
import os
import pwd
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from router_shared import emulator_setup as setup


class EmulatorSetupTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name).resolve(); self.configs=self.root/'configs'
        self.config=self.configs/'samcoupe/emulators.cfg'; self.config.parent.mkdir(parents=True)
        self.fallback='/opt/user-original --disk %ROM%'
        self.config.write_text('default = "simcoupe"\n# preserve comment\nsimcoupe = "'+self.fallback+'"\nother = "other %ROM%"\n')
        self.provider=self.root/'lib/router_shared/emulator_hosts.py'; self.provider.parent.mkdir(parents=True); self.provider.touch()
        self.native_module=self.provider.parent/'retropie_native.py'; self.native_module.write_text('FALLBACK_COMMAND_SCHEMA = 1\n')
        from router_shared import retropie_native
        self.module_path_patch=patch.object(retropie_native,'__file__',str(self.native_module));self.module_path_patch.start();self.addCleanup(self.module_path_patch.stop)
        self.launcher=self.root/'native-route'
        self.launcher.write_text("#!/usr/bin/python3\nimport sys\nsys.path.insert(0, %r)\nfrom router_shared.retropie_native import main\nsys.exit(main())\n" % str(self.provider.parent.parent))
        self.launcher.chmod(0o755)
        self.computer_launcher=self.root/'computer-launch'
        self.emulator=self.root/'simcoupe';self.emulator.touch();self.emulator.chmod(0o755)
        self.registry=self.root/'registry.json';self.manifest=self.root/'manifest.json'; self.state=self.root/'state'
        self.user=pwd.getpwuid(os.getuid()).pw_name
        self.sha=hashlib.sha256(self.fallback.encode()).hexdigest()
        self.command='%s simcoupe -- %s %%ROM%%' % (self.computer_launcher,self.emulator)
    def plan(self, **kw):
        options=dict(profile='simcoupe',choice='simcoupe',routed_command=self.command,fallback_sha256=self.sha,
                     configs=self.configs,registry_path=self.registry,manifest_path=self.manifest,provider=self.provider,
                     native_launcher=self.launcher,runtime_user=self.user,state_root=self.state,computer_launcher=self.computer_launcher)
        options.update(kw);return setup.plan(**options)

    def test_explicit_setup_preserves_fallback_default_other_entries_and_repeats(self):
        changes=self.plan(); self.assertFalse(self.registry.exists()); self.assertEqual(self.config.read_text().count('default = "simcoupe"'),1)
        backup=setup.apply_plan(changes,self.root/'backups',lambda:False,(self.computer_launcher,))
        doc=json.loads(self.registry.read_text()); entry=doc['entries']['router-samcoupe-simcoupe']
        self.assertEqual(entry['fallback_command'],self.fallback);self.assertEqual(entry['fallback_sha256'],self.sha)
        self.assertEqual(entry['command'],self.command);self.assertTrue(entry['private_bridge'])
        self.assertIn('default = "simcoupe"\n# preserve comment\n',self.config.read_text())
        self.assertIn('other = "other %ROM%"',self.config.read_text())
        manifest=json.loads(self.manifest.read_text());self.assertEqual(manifest['systems'][str(self.config)]['kind'],'native')
        self.assertTrue((backup/'files.json').is_file())
        again=self.plan();self.assertIsNone(setup.apply_plan(again,self.root/'backups',lambda:False,(self.computer_launcher,)))

    def test_installed_entry_preserves_disabled_passthrough(self):
        import argparse
        from router_shared import retropie_native
        changes=self.plan();setup.apply_plan(changes,self.root/'backups',lambda:False,(self.computer_launcher,))
        entry=json.loads(self.registry.read_text())['entries']['router-samcoupe-simcoupe']
        args=argparse.Namespace(entry='router-samcoupe-simcoupe',rom='/tmp/name with spaces.dsk',basename='test',xres='',yres='',test_seconds=0,inspect=False)
        with patch.object(retropie_native.os,'geteuid',return_value=123), patch.object(retropie_native,'UID',123), \
             patch.object(retropie_native,'registry',return_value={args.entry:entry}), \
             patch('router_shared.native_sessions.launch_policy',return_value={'physical_scope':'nes'}), \
             patch.object(retropie_native.os,'execv') as execute, patch.object(retropie_native,'inputs') as inputs:
            retropie_native.prepare(args)
        self.assertEqual(execute.call_args[0][0],'/bin/bash')
        self.assertEqual(execute.call_args[0][1][-1],"/opt/user-original --disk '/tmp/name with spaces.dsk'")
        inputs.assert_not_called()
        entry['fallback_sha256'] = '0' * 64
        with patch.object(retropie_native.os,'geteuid',return_value=123), patch.object(retropie_native,'UID',123), \
             patch.object(retropie_native,'registry',return_value={args.entry:entry}), \
             patch('router_shared.native_sessions.launch_policy',return_value={'physical_scope':'nes'}), \
             patch.object(retropie_native.os,'execv') as execute:
            with self.assertRaisesRegex(ValueError,'CHECKSUM_MISMATCH'):
                retropie_native.prepare(args)
        execute.assert_not_called()

    def test_rejects_unverified_altered_or_inappropriate_fallback(self):
        for options in ({'fallback_sha256':'0'*64}, {'routed_command':self.command.replace('simcoupe --','gsplus --')},
                        {'routed_command':self.command.replace('%ROM%','prefix%ROM%')}, {'choice':'missing'}):
            with self.assertRaises(ValueError):self.plan(**options)
        self.config.write_text('simcoupe = "CON:/opt/other %ROM%"\n')
        with self.assertRaises(ValueError):self.plan(fallback_sha256=setup.digest('CON:/opt/other %ROM%'))
        self.assertFalse(self.registry.exists())
        unsafe = '/opt/original --disk "%ROM%"'
        self.config.write_text('simcoupe = "'+unsafe.replace('"', r'\"')+'"\n')
        with self.assertRaises(ValueError):
            self.plan(fallback_sha256=setup.digest(unsafe))
        unsafe = "/opt/original --disk '%ROM%'"
        self.config.write_text('simcoupe = "'+unsafe+'"\n')
        with self.assertRaisesRegex(ValueError,'standalone'):
            self.plan(fallback_sha256=setup.digest(unsafe))
        unsafe = '/opt/original --disk=prefix%ROM%'
        self.config.write_text('simcoupe = "'+unsafe+'"\n')
        with self.assertRaisesRegex(ValueError,'standalone'):
            self.plan(fallback_sha256=setup.digest(unsafe))

    def test_conflicts_and_active_game_do_not_write(self):
        self.registry.write_text(json.dumps({'entries':{'router-samcoupe-simcoupe':{'command':'user'}},
             'runtime':{'user':self.user,'state_root':str(self.state),'launcher':str(self.launcher)}}))
        before=self.registry.read_bytes()
        with self.assertRaisesRegex(ValueError,'conflicts'):self.plan()
        self.assertEqual(self.registry.read_bytes(),before)
        self.registry.unlink();changes=self.plan()
        with self.assertRaisesRegex(RuntimeError,'active game'):setup.apply_plan(changes,self.root/'backups',lambda:True)
        self.assertFalse(self.registry.exists());self.assertEqual(self.config.read_text().splitlines()[2], 'simcoupe = "'+self.fallback+'"')

    def test_rejects_default_selector_and_unsupported_shell_syntax(self):
        with self.assertRaisesRegex(ValueError,'Unsupported profile'):
            self.plan(choice='default')
        for command in ("/opt/original --disk ' %ROM% '", '/opt/original --disk " %ROM% "',
                        '/opt/original --disk=prefix%ROM%', '/opt/original %ROM% ; touch /tmp/no',
                        '/opt/original %ROM% | cat', '/opt/original $(whoami) %ROM%',
                        '/opt/original \\%ROM%', '/opt/original foo\\ %ROM%', '/opt/original [ab] %ROM%', '/opt/original `whoami` %ROM%'):
            self.config.write_text('simcoupe = "'+command+'"\n')
            with self.assertRaises(ValueError, msg=command):
                self.plan(fallback_sha256=setup.digest(command))

    def test_rejects_mismatched_native_launcher_or_library(self):
        self.launcher.write_text('#!/usr/bin/python3\nprint("stale launcher")\n')
        with self.assertRaisesRegex(ValueError,'matching Router'):
            self.plan()
        self.launcher.write_text("#!/usr/bin/python3\nimport sys\nsys.path.insert(0, %r)\nfrom router_shared.retropie_native import main\nsys.exit(main())\n" % str(self.provider.parent.parent))
        from router_shared import retropie_native
        with patch.object(retropie_native,'__file__',str(self.root/'unrelated.py')):
            with self.assertRaisesRegex(ValueError,'beside the provider'):
                self.plan()
        self.assertFalse(self.registry.exists())

    def test_incompatible_native_runtime_refuses_before_writing(self):
        from router_shared import retropie_native
        with patch.object(retropie_native,'FALLBACK_COMMAND_SCHEMA',None):
            with self.assertRaisesRegex(ValueError,'upgrade Router'):
                self.plan()
        self.assertFalse(self.registry.exists()); self.assertFalse(self.computer_launcher.exists())

    def test_installed_fresh_entry_is_idempotently_auto_discovered(self):
        from router_shared.emulator_registration import auto_register
        changes=self.plan(); setup.apply_plan(changes,self.root/'backups',lambda:False,(self.computer_launcher,))
        before=self.manifest.read_bytes()
        self.assertFalse(auto_register(self.provider,self.configs,self.registry,self.manifest))
        self.assertEqual(self.manifest.read_bytes(),before)

    def test_game_start_during_install_rolls_back(self):
        changes=self.plan(); before=self.config.read_bytes(); checks=iter([False,False,False,True])
        with self.assertRaisesRegex(RuntimeError,'game started'):
            setup.apply_plan(changes,self.root/'backups',lambda:next(checks),(self.computer_launcher,))
        self.assertEqual(self.config.read_bytes(),before)
        self.assertFalse(self.registry.exists());self.assertFalse(self.computer_launcher.exists())

    def test_stale_plan_refuses_to_replace_user_changes(self):
        changes=self.plan(); self.config.write_text('user changed this file\n')
        with self.assertRaisesRegex(RuntimeError,'changed after preparation'):
            setup.apply_plan(changes,self.root/'backups',lambda:False,(self.computer_launcher,))
        self.assertEqual(self.config.read_text(),'user changed this file\n')
        self.assertFalse(self.registry.exists())

    def test_write_failure_rolls_back_originals(self):
        changes=self.plan(); original=self.config.read_bytes(); real=setup.atomic_write;calls=[]
        def write(path,text,mode=0o644):
            calls.append(path)
            if len(calls)==3: raise OSError('simulated full disk')
            return real(path,text,mode)
        with patch.object(setup,'atomic_write',side_effect=write):
            with self.assertRaisesRegex(OSError,'full disk'):setup.apply_plan(changes,self.root/'backups',lambda:False,(self.computer_launcher,))
        self.assertEqual(self.config.read_bytes(),original);self.assertFalse(self.registry.exists());self.assertFalse(self.manifest.exists())

    def test_explicit_player_routing_and_bounds(self):
        for player in ('1','2','3','4'):
            command='%s --player %s simcoupe -- %s %%ROM%%' % (self.computer_launcher,player,self.emulator)
            changes=self.plan(routed_command=command)
            entry=json.loads(changes[self.registry])['entries']['router-samcoupe-simcoupe']
            self.assertEqual(entry['command'],command)
        for player in ('0','5','-1'):
            command='%s --player %s simcoupe -- %s %%ROM%%' % (self.computer_launcher,player,self.emulator)
            with self.assertRaises(ValueError):self.plan(routed_command=command)
