import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from router_shared.emulator_registration import register


class RegistrationTests(unittest.TestCase):
    def test_merge_repeat_and_stale_rejection(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); provider = root / 'host.py'; provider.touch()
            config = root / 'emulators.cfg'; command = '/some/qualified/launcher %ROM%'
            config.write_text('simcoupe = "' + command + '"\n')
            digest = hashlib.sha256(command.encode()).hexdigest()
            manifest = root / 'adapters.json'
            existing = {'schema': 1, 'extra': 'preserved', 'providers': [{'path': '/existing'}], 'systems': {'/other': {'system': 'nes'}}}
            manifest.write_text(json.dumps(existing))
            spec = root / 'qualification.json'
            spec.write_text(json.dumps({'schema': 1, 'systems': [{'config': str(config), 'system': 'samcoupe', 'kind': 'native', 'command_sha256': [digest]}]}))
            self.assertTrue(register(provider, spec, manifest))
            result = json.loads(manifest.read_text())
            self.assertEqual(result['extra'], 'preserved')
            self.assertEqual(result['providers'][0], {'path': '/existing'})
            self.assertEqual(result['systems']['/other'], {'system': 'nes'})
            self.assertEqual(result['systems'][str(config)]['command_sha256'], [digest])
            self.assertFalse(register(provider, spec, manifest))
            before = manifest.read_bytes(); config.write_text('simcoupe = "changed"\n')
            with self.assertRaises(ValueError): register(provider, spec, manifest)
            self.assertEqual(manifest.read_bytes(), before)

    def test_absent_spec_is_noop(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.assertFalse(register(root/'missing-provider', root/'missing-spec', root/'manifest'))
            self.assertFalse((root/'manifest').exists())

class AutomaticDiscoveryTests(unittest.TestCase):
    def test_discovers_only_explicit_private_registered_bridges(self):
        from router_shared.emulator_registration import auto_register
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); configs = root / 'configs'; config = configs / 'samcoupe/emulators.cfg'
            config.parent.mkdir(parents=True)
            launcher = root / 'native-route.py'; launcher.touch()
            target = root / 'sam-launch.py'; target.touch()
            provider = root / 'provider.py'; provider.touch()
            command = '/usr/bin/python3 %s --entry samcoupe--simcoupe --rom %%ROM%%' % launcher
            config.write_text('default = "simcoupe"\nsimcoupe = "' + command + '"\n')
            registry = root / 'registry.json'
            entry = {'system': 'samcoupe', 'emulator': 'simcoupe', 'config': str(config),
                     'command': '/usr/bin/python3 %s %%ROM%%' % target, 'private_bridge': True}
            registry.write_text(json.dumps({'runtime': {'launcher': str(launcher)}, 'entries': {'samcoupe--simcoupe': entry}}))
            manifest = root / 'adapters.json'
            self.assertTrue(auto_register(provider, configs, registry, manifest))
            result = json.loads(manifest.read_text())
            self.assertEqual(result['systems'][str(config)]['command_sha256'], [hashlib.sha256(command.encode()).hexdigest()])
            self.assertFalse(auto_register(provider, configs, registry, manifest))
            config.write_text('simcoupe = "' + command.replace('samcoupe--simcoupe', 'other') + '"\n')
            before = manifest.read_bytes()
            self.assertFalse(auto_register(provider, configs, registry, manifest))
            self.assertEqual(before, manifest.read_bytes())
