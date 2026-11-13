import argparse
import unittest
from unittest.mock import patch
from router_shared import retropie_native as native

class NativeFallbackTests(unittest.TestCase):
    def test_disabled_entry_executes_qualified_fallback_and_quotes_rom(self):
        args=argparse.Namespace(rom='/roms/Title with spaces.dsk',basename='Title',xres='',yres='',entry='game',test_seconds=0,inspect=False)
        entry={'system':'samcoupe','command':'python3 -m router_shared.computer_launch simcoupe -- /emulator %ROM%',
               'fallback_command':'/original/launcher %ROM%','private_bridge':True}
        with patch.object(native.os,'geteuid',return_value=123),patch.object(native,'UID',123),patch.object(native,'registry',return_value={'game':entry}),patch('router_shared.native_sessions.launch_policy',return_value={'physical_scope':'nes'}),patch.object(native.os,'execv',return_value=None) as execute,patch.object(native,'inputs') as inputs,patch.object(native.subprocess,'run') as run:
            native.prepare(args)
        execute.assert_called_once_with('/bin/bash',['bash','-c',"/original/launcher '/roms/Title with spaces.dsk'"])
        inputs.assert_not_called();run.assert_not_called()
        self.assertEqual(entry['command'],'python3 -m router_shared.computer_launch simcoupe -- /emulator %ROM%')

    def test_legacy_passthrough_preserved_and_invalid_fallback_rejected(self):
        args=argparse.Namespace(rom='/rom.dsk',basename='rom',xres='',yres='')
        with patch.object(native.os,'execv') as execute:
            native.passthrough(args,{'command':'/original %ROM%'})
        execute.assert_called_once_with('/bin/bash',['bash','-c','/original /rom.dsk'])
        with self.assertRaisesRegex(ValueError,'INVALID_NATIVE_FALLBACK'):
            native.passthrough(args,{'command':'/original %ROM%','fallback_command':''})

class QualifiedFallbackTests(unittest.TestCase):
    def test_detects_changed_or_missing_attested_command(self):
        import hashlib
        args=argparse.Namespace(rom='/rom.dsk',basename='rom',xres='',yres='')
        command='/safe/original %ROM%'
        digest=hashlib.sha256(command.encode()).hexdigest()
        with patch.object(native.os,'execv') as execute:
            native.passthrough(args,{'command':'/router %ROM%', 'fallback_command':command,'fallback_sha256':digest})
        execute.assert_called_once_with('/bin/bash',['bash','-c','/safe/original /rom.dsk'])
        for entry in ({'command':'/router','fallback_command':'/changed','fallback_sha256':digest},
                      {'command':'/router','fallback_sha256':digest}):
            with self.assertRaisesRegex(ValueError,'CHECKSUM_MISMATCH'):
                native.passthrough(args,entry)
