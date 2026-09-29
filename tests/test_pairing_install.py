import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from router_shared.pairing import load_json, write_json
from router_shared import pairing_install

class PairingInstallerTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)/'link'
        self.platform=patch.object(pairing_install,'platform_name',return_value='launchbox');self.platform.start()
        self.environment=patch.dict(os.environ,APPDATA=self.temp.name);self.environment.start()
    def tearDown(self):self.environment.stop();self.platform.stop();self.temp.cleanup()
    def descriptor(self):return {'kind':'json','token_file':str(self.root.parent/'token'),'target_file':str(self.root.parent/'launcher.json')}
    def test_repeat_install_and_adding_app_keep_connection(self):
        pairing_install.install('virtualglove',self.descriptor(),root=self.root,execute=False)
        write_json(self.root/'connection.json',{'token':'retained-private-secret'})
        pairing_install.install('rob_vision',self.descriptor(),root=self.root,execute=False)
        self.assertEqual(set(load_json(self.root/'adapters.json')),{'virtualglove','rob_vision'})
        self.assertEqual(load_json(self.root/'connection.json')['token'],'retained-private-secret')
        self.assertTrue((self.root.parent/'software/router_shared/pairing_console.py').exists())
        self.assertIn('exec sudo -- "$0"', (self.root.parent/'pair-console').read_text())
    def test_newer_service_retained_and_new_product_registered(self):
        pairing_install.install(None,None,root=self.root,execute=False)
        software=self.root.parent/'software'
        (software/'VERSION').write_text('99.0.0')
        marker=software/'router_shared/pairing_console.py';marker.write_text('newer implementation')
        launcher=self.root.parent/'pair-console';launcher.write_text('newer pairing helper')
        pairing_install.install('rob_vision',self.descriptor(),root=self.root,execute=False)
        self.assertEqual(marker.read_text(),'newer implementation')
        self.assertEqual(launcher.read_text(),'newer pairing helper')
        self.assertIn('rob_vision',load_json(self.root/'adapters.json'))
    def test_interrupted_upgrade_restores_software_and_registration(self):
        pairing_install.install('virtualglove',self.descriptor(),root=self.root,execute=False)
        marker=self.root.parent/'software/router_shared/pairing_console.py';before=marker.read_bytes()
        previous=(self.root/'adapters.json').read_bytes()
        def fail(*args,**kwargs):
            marker.write_text('broken')
            write_json(self.root/'adapters.json',{'bad':True})
            raise OSError('failed startup')
        with patch.object(pairing_install,'_install',side_effect=fail),self.assertRaises(OSError):
            pairing_install.install('rob_vision',self.descriptor(),root=self.root,execute=False)
        self.assertEqual(marker.read_bytes(),before)
        self.assertEqual((self.root/'adapters.json').read_bytes(),previous)
