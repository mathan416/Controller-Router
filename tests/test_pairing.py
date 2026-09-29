import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path
from router_shared.pairing import secret, load_json, write_json, parse_code, connection_code, legacy_proof
from router_shared.pairing_console import LinkStore


class ConsolePairingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.now = 100
        self.restarted = []
        self.store = LinkStore(self.root / 'link', clock=lambda: self.now,
            restart=lambda app, descriptor: self.restarted.append(app), game_active=lambda: False)
        self.token = self.root / 'token'; self.token.write_text('old-secret')
        self.target = self.root / 'launcher.json'; self.target.write_text('{"uno_q":"old.local","keep":42}')
        self.store.register('virtualglove', {'kind': 'json', 'token_file': str(self.token),
            'target_file': str(self.target)})
        self.payload = {'uno_id': '1' * 32, 'uno_url': 'http://uno.local', 'token': secret(),
            'credentials': {'virtualglove': {'token': secret(), 'console_id': '2' * 32}}}
        write_json(self.store.root / 'window.json', {'authorization':'ABCDEFGHIJKL', 'expires':400})

    def tearDown(self): self.temp.cleanup()

    def prepare(self):
        return self.store.prepare(self.payload, authorization='ABCDEFGHIJKL')['transaction']

    def test_commit_keeps_unrelated_settings_and_private_files(self):
        tx = self.prepare(); self.store.commit(tx, self.payload['token']); self.store.finalize(tx, self.payload['token'])
        self.assertEqual(load_json(self.target), {'uno_q':'uno.local', 'keep':42})
        self.assertEqual(self.token.read_text().strip(), self.payload['credentials']['virtualglove']['token'])
        self.assertEqual(os.stat(self.store.root / 'connection.json').st_mode & 0o777, 0o600)
        self.assertNotIn('token', json.dumps(self.store.public()))

    def test_attempt_lockout_and_replay(self):
        for _ in range(5):
            with self.assertRaises(ValueError): self.store.prepare(self.payload, authorization='WRONG')
        with self.assertRaises(ValueError): self.prepare()

    def test_used_code_cannot_be_replayed(self):
        tx = self.prepare(); self.store.abort(tx, self.payload['token'])
        with self.assertRaises(ValueError): self.prepare()

    def test_failed_restart_restores_previous_files(self):
        tx = self.prepare()
        def fail(*_): raise OSError('startup failed')
        self.store.restart = fail
        with self.assertRaises(ValueError): self.store.commit(tx, self.payload['token'])
        self.assertEqual(self.token.read_text(), 'old-secret')
        self.assertEqual(load_json(self.target)['uno_q'], 'old.local')

    def test_expiry_rolls_back_and_game_blocks(self):
        self.prepare(); self.now = 300; self.store.expire()
        self.assertFalse((self.store.root / 'pending.json').exists())
        self.store.game_active = lambda: True
        with self.assertRaises(ValueError): self.store.prepare(self.payload, authorization='ABCDEFGHIJKL')

    def test_code_binds_certificate(self):
        first = connection_code(b'first-cert','ABCDEFGHIJKL')
        second = connection_code(b'second-cert','ABCDEFGHIJKL')
        self.assertNotEqual(parse_code(first)[0], parse_code(second)[0])

    def test_migration_requires_fresh_authenticated_transcript(self):
        self.token.write_text('existing-legacy-secret')
        nonce = 'a' * 32
        proof = self.store.proof('virtualglove', nonce, 'b' * 64)
        transcript = json.dumps(self.payload, sort_keys=True, separators=(',', ':'))
        signed = legacy_proof('existing-legacy-secret', nonce + '\n' + transcript, self.store.console_id, 'b' * 64)
        request = {'nonce':nonce, 'proof':signed, 'connection':self.payload}
        tx = self.store.adopt(request)['transaction']
        self.store.commit(tx, self.payload['token']); self.store.finalize(tx, self.payload['token'])
        with self.assertRaises(ValueError):self.store.adopt(request)
        self.assertNotIn('existing-legacy-secret', json.dumps(proof))

    def test_tampered_migration_keeps_old_connection(self):
        self.token.write_text('existing-legacy-secret')
        nonce = 'a' * 32
        self.store.proof('virtualglove', nonce, 'b' * 64)
        with self.assertRaises(ValueError):
            self.store.adopt({'nonce':nonce,'proof':'0'*64,'connection':self.payload})
        self.assertFalse(self.store.connection)
        self.assertEqual(self.token.read_text(), 'existing-legacy-secret')

    def test_one_legacy_app_cannot_take_over_the_other(self):
        self.token.write_text('existing-virtualglove-secret')
        other = self.root / 'buddy.token'; other.write_text('existing-buddy-secret')
        self.store.register('rob_vision', {'kind': 'json', 'token_file': str(other),
            'target_file': str(self.root / 'buddy.json')})
        nonce = 'c' * 32
        self.store.proof('virtualglove', nonce, 'b' * 64)
        transcript = json.dumps(self.payload, sort_keys=True, separators=(',', ':'))
        signed = legacy_proof('existing-virtualglove-secret', nonce+'\n'+transcript,
                              self.store.console_id, 'b'*64)
        with self.assertRaisesRegex(ValueError, 'Every existing app'):
            self.store.adopt({'nonce':nonce, 'proof':signed, 'connection':self.payload})
        self.assertFalse(self.store.connection)
        self.assertEqual(other.read_text(), 'existing-buddy-secret')

    def test_recovery_failure_retains_journal(self):
        tx = self.prepare()
        self.store.restart = lambda *_: (_ for _ in ()).throw(OSError('offline'))
        with self.assertRaises(ValueError): self.store.commit(tx, self.payload['token'])
        self.assertTrue((self.store.root/'pending.json').exists())
        self.store.restart = lambda *_: None
        self.store.abort(tx, self.payload['token'])
        self.assertFalse((self.store.root/'pending.json').exists())

    def test_revoke_preserves_other_app(self):
        tx = self.prepare(); self.store.commit(tx, self.payload['token']); self.store.finalize(tx, self.payload['token'])
        self.store.revoke('virtualglove', self.payload['token'])
        self.assertEqual(self.token.read_bytes(), b'')
        self.assertTrue(self.store.connection['token'])


if __name__ == '__main__': unittest.main()
