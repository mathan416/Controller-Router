import http.client
import multiprocessing
import socket
import ssl
import tempfile
import time
import unittest
from unittest.mock import patch
from pathlib import Path

class PairingAddressTests(unittest.TestCase):
    def test_console_port_preserves_existing_game_registry_service(self):
        from router_shared.pairing import PORT
        self.assertEqual(PORT, 55359)

    def test_installer_uses_lan_route_without_docker_bridges(self):
        from uno_portal.host.secure_pairing import lan_addresses
        with patch('subprocess.check_output', return_value='[{"prefsrc":"10.0.2.105","dev":"end0"}]'):
            self.assertEqual(lan_addresses(), ['10.0.2.105'])

def start_browser(root, port):
    from uno_portal.host import secure_pairing
    secure_pairing.PORT = port
    class Manager:
        def inspect(self): return {'consoles': []}
        def operation(self, payload, host): return {'accepted': True}
    secure_pairing.serve(Manager(), root, '127.0.0.1', port)

class BrowserPairingTLSTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        with socket.socket() as sock:
            sock.bind(('127.0.0.1',0)); self.port=sock.getsockname()[1]
        self.process=multiprocessing.Process(target=start_browser,args=(Path(self.temp.name),self.port))
        self.process.start()
        for _ in range(100):
            try:
                self.request('GET','/setup'); break
            except OSError: time.sleep(.02)
        else:self.fail('Secure Setup failed to start')
    def tearDown(self):self.process.terminate();self.process.join(5);self.temp.cleanup()
    def request(self,method,path,body=None,headers=None):
        connection=http.client.HTTPSConnection('127.0.0.1',self.port,context=ssl._create_unverified_context(),timeout=3)
        try:
            connection.request(method,path,body,headers or {})
            response=connection.getresponse();return response.status,response.read()
        finally:connection.close()
    def test_same_origin_and_action_header_required(self):
        host='127.0.0.1:'+str(self.port)
        headers={'Host':host,'Origin':'https://'+host,'Content-Type':'application/json','X-Controller-Router-Action':'pairing'}
        self.assertEqual(self.request('POST','/api/pairing','{}',headers)[0],200)
        headers['Origin']='https://attacker.invalid'
        self.assertEqual(self.request('POST','/api/pairing','{}',headers)[0],400)
        headers['Origin']='https://'+host;headers.pop('X-Controller-Router-Action')
        self.assertEqual(self.request('POST','/api/pairing','{}',headers)[0],400)
    def test_page_and_certificate_download_and_bounded_request(self):
        self.assertEqual(self.request('GET','/setup')[0],200)
        status,body=self.request('GET','/certificate.pem')
        self.assertEqual(status,200);self.assertIn(b'BEGIN CERTIFICATE',body)
        host='127.0.0.1:'+str(self.port)
        headers={'Host':host,'Origin':'https://'+host,'Content-Type':'application/json','X-Controller-Router-Action':'pairing'}
        self.assertEqual(self.request('POST','/api/pairing',' '*4097,headers)[0],400)
