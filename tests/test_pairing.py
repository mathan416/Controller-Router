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

    def test_restored_commit_failure_clears_journal_once(self):
        tx = self.prepare()
        calls = []
        def restart(app, _descriptor):
            calls.append(app)
            if len(calls) == 1: raise OSError('startup failed')
        self.store.restart = restart
        with self.assertRaises(ValueError): self.store.commit(tx, self.payload['token'])
        self.assertFalse((self.store.root / 'pending.json').exists())
        self.assertEqual(self.token.read_text(), 'old-secret')
        self.now = 300; self.store.expire()
        self.assertEqual(calls, ['virtualglove', 'virtualglove'])  # no second restore on expiry

    def test_buddy_must_stay_on_player_two_for_save_and_rollback(self):
        from router_shared.pairing_console import check_buddy
        buddy = {'name': 'R.O.B. Vision Controller 2'}
        def config(player): return {'players': [{'player': player, 'sources': [buddy]}]}
        backup = self.root / 'router.json.previous'
        class Router:
            def __init__(self, proposed): self.proposed, self.backup = proposed, backup
            def _materialize(self, _config): return self.proposed
        with self.assertRaisesRegex(ValueError, 'Player 2'):
            check_buddy(Router(config(1)), 'save', {}, True)
        check_buddy(Router(config(2)), 'save', {}, True)
        check_buddy(Router(config(1)), 'save', {}, False)  # R.O.B. Vision not paired
        check_buddy(Router(None), 'rollback', None, True)   # no backup: operate() reports it
        from unittest import mock
        with mock.patch('router_shared.controller_router.load_config', return_value=config(1)):
            backup.write_text('{}')
            with self.assertRaisesRegex(ValueError, 'Player 2'):
                check_buddy(Router(None), 'rollback', None, True)
        with mock.patch('router_shared.controller_router.load_config', return_value=config(2)):
            check_buddy(Router(None), 'rollback', None, True)
        check_buddy(Router(None), 'check', None, True)

    def test_env_and_text_adapters_use_descriptor_key_and_port(self):
        url = 'http://uno.local'
        env = self.root / 'receiver.env'
        cases = (({'kind': 'env'}, 'A=1\nROB_VISION_URL=old\n', 'A=1\nROB_VISION_URL=http://uno.local:8766\n'),
                 ({'kind': 'env', 'target_key': 'GLOVE_URL', 'port': 9000}, 'GLOVE_URL=old\nROB_VISION_URL=keep\n',
                  'GLOVE_URL=http://uno.local:9000\nROB_VISION_URL=keep\n'),
                 ({'kind': 'text'}, '', 'http://uno.local:8766\n'),
                 ({'kind': 'text', 'port': 8101}, '', 'http://uno.local:8101\n'))
        for extra, before, after in cases:
            with self.subTest(extra=extra):
                env.write_text(before)
                self.store.register('rob_vision', {**extra, 'token_file': str(self.root / 'buddy.token'),
                                                   'target_file': str(env)})
                self.store._apply('rob_vision', {'token': secret(), 'console_id': '3' * 32}, url)
                self.assertEqual(env.read_text(), after)
        for bad in ({'kind': 'text', 'port': 0}, {'kind': 'text', 'port': '8766'},
                    {'kind': 'env', 'target_key': 'X=1\nY'}, {'kind': 'env', 'target_key': 'lower'}):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                self.store.register('rob_vision', {**bad, 'token_file': str(self.root / 'buddy.token'),
                                                   'target_file': str(env)})

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

    def test_legacy_proof_endpoint_cannot_sign_an_adopt_transcript(self):
        self.token.write_text('existing-legacy-secret')
        nonce = 'a' * 16
        self.store.proof('virtualglove', nonce, 'b' * 64)
        document = {'token': 'A' * 32, 'uno_id': 'a' * 32, 'uno_url': 'http://a'}
        transcript = json.dumps(document, sort_keys=True, separators=(',', ':'))
        with self.assertRaises(ValueError):
            self.store.proof('virtualglove', nonce + '\n' + transcript, 'b' * 64)
        for bad in ('A' * 32, 'g' * 32, 'a' * 15, 'a' * 129, 'a' * 16 + '\n'):
            with self.assertRaises(ValueError):
                self.store.proof('virtualglove', bad, 'b' * 64)
        self.assertFalse(self.store.connection)
        self.assertEqual(self.token.read_text(), 'existing-legacy-secret')

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
