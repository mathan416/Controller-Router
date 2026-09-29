"""Exercise certificate pinning against the actual HTTPS console service."""
import json
import multiprocessing
import socket
import ssl
import tempfile
import time
import unittest
from pathlib import Path
from router_shared.pairing import Peer, certificate_code, fingerprint, secret, write_json
from router_shared.pairing_console import LinkStore, ensure_certificate, serve

class PairingTLSTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.store = LinkStore(self.root)
        cert, _ = ensure_certificate(self.root)
        self.der = ssl.PEM_cert_to_DER_cert(cert.read_text())
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0)); self.port = sock.getsockname()[1]
        self.process = multiprocessing.Process(target=serve, args=(self.root, '127.0.0.1', self.port))
        self.process.start()
        self.peer = Peer('console.local', pin=fingerprint(self.der), port=self.port, resolve=lambda _: '127.0.0.1')
        for _ in range(50):
            try:
                self.peer.request('/identity'); break
            except OSError: time.sleep(.02)
        else: self.fail('TLS service failed to start')
    def tearDown(self):
        self.process.terminate(); self.process.join(5); self.temp.cleanup()
    def payload(self):
        return {'uno_id': '1'*32, 'uno_url': 'http://uno.local', 'token': secret(), 'credentials': {}, 'authorization':'ABCDEFGHIJKL'}
    def test_pin_mismatch_prevents_submission(self):
        write_json(self.root/'window.json', {'authorization':'ABCDEFGHIJKL','expires':time.time()+300})
        wrong = Peer('console.local', pin='0'*64, port=self.port, resolve=lambda _: '127.0.0.1')
        with self.assertRaisesRegex(ValueError, 'certificate changed'): wrong.request('/pair',self.payload())
        window=json.loads((self.root/'window.json').read_text())
        self.assertFalse(window.get('used')); self.assertEqual(window.get('attempts',0),0)
    def test_pinned_pair_commit_replay_and_redaction(self):
        write_json(self.root/'window.json', {'authorization':'ABCDEFGHIJKL','expires':time.time()+300})
        peer=Peer('console.local',code_pin=certificate_code(self.der),port=self.port,resolve=lambda _: '127.0.0.1')
        payload=self.payload(); tx=peer.request('/pair',payload)['transaction']
        peer.request('/manage',{'operation':'commit','transaction':tx},token=payload['token'])
        peer.request('/manage',{'operation':'finalize','transaction':tx},token=payload['token'])
        public=peer.request('/identity')
        self.assertTrue(public['paired']); self.assertNotIn(payload['token'],json.dumps(public))
        with self.assertRaises(ValueError): peer.request('/pair',payload)
    def test_expired_code_and_attempt_limit(self):
        write_json(self.root/'window.json', {'authorization':'ABCDEFGHIJKL','expires':time.time()-1})
        with self.assertRaises(ValueError):self.peer.request('/pair',self.payload())
        write_json(self.root/'window.json', {'authorization':'ABCDEFGHIJKL','expires':time.time()+300})
        for _ in range(5):
            payload=self.payload();payload['authorization']='BAD'
            with self.assertRaises(ValueError):self.peer.request('/pair',payload)
        with self.assertRaises(ValueError):self.peer.request('/pair',self.payload())
