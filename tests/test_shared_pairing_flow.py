import copy
import json
import tempfile
import unittest
from pathlib import Path
from router_shared.pairing import secret, write_json
from router_shared.pairing_console import LinkStore
from uno_portal.host.pairing import PairingManager


class Adapters:
    def __init__(self):
        self.apps = {'virtualglove', 'rob_vision'}
        self.records = {app: {} for app in self.apps}
        self.fail = None
    def installed(self): return self.apps
    def request(self, app, operation, **payload):
        if self.fail == (app, operation): raise OSError('unavailable')
        if operation == 'export': return copy.deepcopy(self.records[app])
        if operation == 'restore': self.records[app] = payload['snapshot']
        if operation == 'import': self.records[app] = {'record':payload['record']}
        if operation == 'remove': self.records[app] = {}
        return {'ready':True}


class Matrix:
    available = True
    def begin_pairing(self, identity, pin): self.pin = pin; return self.available
    def clear_pairing(self): pass


class SharedPairingFlowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.root = Path(self.temp.name)
        self.store = LinkStore(self.root/'console', restart=lambda *_: None, game_active=lambda:False)
        for app in ('virtualglove','rob_vision'):
            token=self.root/(app+'.token');token.write_text('prior-token')
            target=self.root/(app+'.json');target.write_text('{"uno_q":"previous.local","players":[1,2]}')
            self.store.register(app,{'kind':'json','token_file':str(token),'target_file':str(target)})
        write_json(self.store.root/'window.json',{'authorization':'ABCDEFGHIJKL','expires':1000})
        self.store.clock=lambda:100
        store=self.store
        class Peer:
            def __init__(peer, host, pin=None, code_pin=None):
                peer.host=host;peer.last_fingerprint='a'*64
            def request(peer,path,payload=None,token=None):
                if path=='/identity': return store.public()
                if path=='/legacy-proof':return store.proof(payload['app'],payload['nonce'],'a'*64)
                if path=='/adopt':return store.adopt(payload)
                if path=='/pair':return store.prepare(payload,authorization=payload['authorization'])
                if path=='/manage':
                    action=payload['operation']
                    if action=='prepare':return store.prepare(payload,token=token)
                    if action=='status':store.authorize(token);return store.public()
                    if action=='remove':return store.revoke(payload.get('app'),token)
                    return getattr(store,action)(payload['transaction'],token)
                raise ValueError('unexpected request')
        self.adapters=Adapters();self.matrix=Matrix();self.active=False
        self.manager=PairingManager(self.matrix,lambda:self.active,self.root/'uno',self.adapters,Peer,clock=lambda:100)
        self.manager.certificate_identity='ABCDEF1'

    def tearDown(self): self.temp.cleanup()
    def begin(self):return self.manager.begin('console.local','CR1-'+'A'*20+'-ABCDEFGHIJKL','uno.local')
    def pair(self):
        start=self.begin();return self.manager.confirm(start['session'],self.matrix.pin)

    def test_both_apps_distinct_credentials_and_browser_redaction(self):
        public=self.pair()
        self.assertEqual(public['consoles'][0]['status'],'Connected')
        record=next(iter(self.manager.document['consoles'].values()))
        tokens=[record['token']]+[value['token'] for value in record['apps'].values()]
        self.assertEqual(len(set(tokens)),3)
        for token in tokens:self.assertNotIn(token,json.dumps(public))
        self.assertNotIn(self.matrix.pin,json.dumps(self.manager.inspect()))
        self.assertFalse((self.manager.root/'pending-connection.json').exists())

    def test_matrix_unavailable_and_live_game_reject(self):
        self.matrix.available=False
        with self.assertRaises(ValueError):self.begin()
        self.matrix.available=True;self.active=True
        with self.assertRaises(ValueError):self.begin()
        self.assertFalse(self.store.connection)

    def test_matrix_attempt_lockout(self):
        session=self.begin()['session']
        for _ in range(5):
            with self.assertRaises(ValueError):self.manager.confirm(session,'wrong')
        with self.assertRaises(ValueError):self.begin()

    def test_partial_product_failure_restores_both_sides(self):
        self.adapters.fail=('rob_vision','import')
        with self.assertRaisesRegex(ValueError, 'R.O.B. Vision needs attention'):self.pair()
        self.assertFalse(self.store.connection)
        self.assertFalse(self.manager.document['consoles'])
        self.assertEqual(self.adapters.records,{'virtualglove':{},'rob_vision':{}})
        self.assertFalse((self.store.root/'pending.json').exists())

    def test_later_install_provisions_without_new_pairing(self):
        self.adapters.apps={'virtualglove'};self.pair()
        self.adapters.apps.add('rob_vision')
        # Legacy discovery is separately tested; no legacy records in this simulation.
        self.manager.import_legacy=lambda:None
        self.manager.reconcile()
        self.assertIn('rob_vision',self.store.connection['apps'])
        self.assertTrue(self.adapters.records['rob_vision']['record'])

    def test_router_alone_and_either_product_alone(self):
        for apps in (set(), {'virtualglove'}, {'rob_vision'}):
            with self.subTest(apps=apps):
                self.adapters.apps = apps
                self.manager.document["consoles"] = {}
                write_json(self.store.root/'window.json',{'authorization':'ABCDEFGHIJKL','expires':1000})
                self.pair()
                self.assertEqual(set(self.store.connection['apps']), apps)

    def test_adding_console_adapter_later_keeps_existing_token(self):
        descriptor = self.store.adapters.pop('rob_vision')
        write_json(self.store.root/'adapters.json', self.store.adapters)
        self.pair()
        original = self.store.connection['apps']['virtualglove']['token']
        self.store.register('rob_vision', descriptor)
        self.manager.import_legacy=lambda:None
        self.manager.reconcile()
        self.assertEqual(self.store.connection['apps']['virtualglove']['token'],original)
        self.assertIn('rob_vision', self.store.connection['apps'])

    def test_independently_expired_console_transaction_recovers(self):
        start = self.begin()
        self.adapters.fail=('rob_vision','import')
        original = self.manager._rollback
        self.manager._rollback=lambda *_:None
        with self.assertRaises(ValueError):self.manager.confirm(start['session'],self.matrix.pin)
        self.store.clock=lambda:1000
        self.store.expire()
        self.manager._rollback=original
        self.adapters.fail=None
        self.manager.reconcile()
        self.assertFalse((self.manager.root/'pending-connection.json').exists())
        self.assertFalse(self.store.connection)

    def test_individual_revocation_then_removal(self):
        self.pair();identity=self.store.console_id
        self.manager.access(identity,'rob_vision',False)
        self.assertIn('virtualglove',self.store.connection['apps'])
        self.assertNotIn('rob_vision',self.store.connection['apps'])
        self.assertTrue(self.adapters.records['virtualglove'])
        self.manager.remove(identity)
        self.assertFalse(self.store.connection)
        self.assertFalse(self.manager.inspect()['consoles'])

    # ---- Halt the controller when the console shuts down ----
    def _enable_halt(self):
        self.pair();identity=self.store.console_id
        (self.manager.root/'.halt-enabled').write_text('')
        start=self.manager.operation({'operation':'halt','id':identity,'enabled':True})
        self.assertFalse(self.manager.inspect()['consoles'][0]['halt_on_shutdown'])  # not until confirmed
        self.manager.confirm(start['session'],self.matrix.pin)
        self.assertTrue(self.manager.inspect()['consoles'][0]['halt_on_shutdown'])
        return identity

    def _notify(self):
        """Run the console's real notifier against this UNO-side manager."""
        import io
        from unittest.mock import patch
        from router_shared.pairing_console import notify_shutdown
        manager=self.manager
        class Reply(io.BytesIO):
            def __enter__(self): return self
            def __exit__(self,*_): self.close()
        def opener(request,timeout):
            self.assertEqual(request.full_url,'http://uno.local/api/console-halt')
            try:
                result=manager.console_halt(json.loads(request.data))
            except ValueError as error:
                result={'error':str(error)}
            return Reply(json.dumps(result).encode())
        class ImmediateTimer:
            def __init__(timer,delay,action): timer.action=action
            def start(timer): timer.action()
        with patch('uno_portal.host.pairing.threading.Timer',ImmediateTimer):
            return notify_shutdown(self.store.root,opener=opener)

    def test_console_shutdown_halts_controller_when_allowed(self):
        self._enable_halt()
        self.assertEqual(self._notify(),'The controller will halt.')
        self.assertEqual((self.manager.root/'halt-request').read_text(),'halt\n')
        self.assertIn('Halt requested',self.manager.inspect()['consoles'][0]['halt_message'])
        self.assertNotIn(self.store.connection['token'],json.dumps(self.manager.inspect()))

    def test_console_shutdown_is_refused_when_off_busy_or_shared(self):
        self.pair()
        self.assertIn('may not halt',self._notify())                    # off by default
        self.assertFalse((self.manager.root/'halt-request').exists())
        self.manager.document['consoles']={};write_json(self.store.root/'window.json',{'authorization':'ABCDEFGHIJKL','expires':1000})
        identity=self._enable_halt()
        self.active=True
        self.assertIn('game was running',self._notify())
        self.assertIn('Not halted',self.manager.inspect()['consoles'][0]['halt_message'])
        self.active=False
        self.manager.document['consoles']['f'*32]={'host':'other.local','platform':'retropie','status':'Connected',
                                                    'token':secret(),'fingerprint':'b'*64,'apps':{}}
        self.assertIn('Another paired console',self._notify())
        del self.manager.document['consoles']['f'*32]
        (self.manager.root/'.halt-enabled').unlink()
        self.assertIn('helper is not installed',self._notify())
        self.assertFalse((self.manager.root/'halt-request').exists())

    def test_halt_request_needs_fresh_signed_single_use_challenge(self):
        from router_shared.pairing import halt_proof
        identity=self._enable_halt();token=self.store.connection['token'];uno=self.manager.document['uno_id']
        nonce=self.manager.halt_challenge(identity)['nonce']
        with self.assertRaisesRegex(ValueError,'not verified'):
            self.manager.halt_request(identity,nonce,'0'*64)            # wrong signature
        with self.assertRaisesRegex(ValueError,'not verified'):
            self.manager.halt_request(identity,nonce,halt_proof(token,uno,identity,nonce))  # nonce already used
        nonce=self.manager.halt_challenge(identity)['nonce']
        self.manager.clock=lambda:100+31
        with self.assertRaisesRegex(ValueError,'not verified'):
            self.manager.halt_request(identity,nonce,halt_proof(token,uno,identity,nonce))  # expired
        self.manager.clock=lambda:100
        nonce=self.manager.halt_challenge(identity)['nonce']
        legacy_style=__import__('router_shared.pairing',fromlist=['legacy_proof']).legacy_proof(token,nonce,identity,uno)
        with self.assertRaisesRegex(ValueError,'not verified'):
            self.manager.halt_request(identity,nonce,legacy_style)       # another proof type cannot pass
        self.assertFalse((self.manager.root/'halt-request').exists())

    def test_halt_setting_needs_helper_and_survives_repairing(self):
        self.pair();identity=self.store.console_id
        with self.assertRaisesRegex(ValueError,'halt helper'):
            self.manager.operation({'operation':'halt','id':identity,'enabled':True})
        self.assertFalse(self.manager.inspect()['halt_helper'])
        self.manager.document['consoles']={};write_json(self.store.root/'window.json',{'authorization':'ABCDEFGHIJKL','expires':1000})
        self._enable_halt()
        write_json(self.store.root/'window.json',{'authorization':'ABCDEFGHIJKL','expires':1000})
        self.pair()                                                       # pair the same console again
        self.assertTrue(self.manager.inspect()['consoles'][0]['halt_on_shutdown'])

    def test_browser_remove_and_access_need_matrix_code(self):
        self.pair();identity=self.store.console_id
        start=self.manager.operation({'operation':'remove','id':identity})
        self.assertIn('session',start)
        self.assertTrue(self.manager.inspect()['consoles'])
        self.assertTrue(self.store.connection)
        with self.assertRaises(ValueError):self.manager.confirm(start['session'],'000000' if self.matrix.pin!='000000' else '111111')
        self.assertTrue(self.manager.inspect()['consoles'])
        self.manager.operation({'operation':'confirm','session':start['session'],'pin':self.matrix.pin})
        self.assertFalse(self.manager.inspect()['consoles'])
        self.assertFalse(self.store.connection)

    def test_browser_access_change_applies_only_after_confirmation(self):
        self.pair();identity=self.store.console_id
        start=self.manager.operation({'operation':'access','id':identity,'app':'rob_vision','enabled':False})
        self.assertIn('rob_vision',self.store.connection['apps'])
        with self.assertRaises(ValueError):
            self.manager.operation({'operation':'remove','id':identity})  # one window at a time
        self.manager.confirm(start['session'],self.matrix.pin)
        self.assertNotIn('rob_vision',self.store.connection['apps'])
        self.assertIn('virtualglove',self.store.connection['apps'])

    def test_change_requests_are_validated_and_lock_out(self):
        self.pair();identity=self.store.console_id
        for payload in ({'operation':'remove','id':'f'*32},
                        {'operation':'access','id':identity,'app':'unknown','enabled':False},
                        {'operation':'access','id':identity,'app':'rob_vision','enabled':'no'}):
            with self.assertRaises(ValueError):self.manager.operation(payload)
        session=self.manager.operation({'operation':'remove','id':identity})['session']
        for _ in range(5):
            with self.assertRaises(ValueError):self.manager.confirm(session,'wrong')
        with self.assertRaises(ValueError):self.manager.operation({'operation':'remove','id':identity})
        self.assertTrue(self.store.connection)

    def test_other_browsers_cannot_end_a_confirmation(self):
        start=self.begin()
        with self.assertRaises(ValueError):self.manager.operation({'operation':'cancel'})
        with self.assertRaises(ValueError):self.manager.operation({'operation':'cancel','session':'0'*32})
        with self.assertRaises(ValueError):self.manager.confirm('0'*32,self.matrix.pin)
        self.assertTrue(self.manager.inspect()['pairing'])
        self.manager.confirm(start['session'],self.matrix.pin)
        self.assertTrue(self.store.connection)

    def test_cancel_with_own_session_and_game_start_close_window(self):
        start=self.begin()
        self.assertEqual(self.manager.operation({'operation':'cancel','session':start['session']}),{'cancelled':True})
        self.assertFalse(self.manager.inspect()['pairing'])
        self.begin();self.manager.close_window()
        self.assertFalse(self.manager.inspect()['pairing'])

    def test_pairing_replaces_unconfirmed_change_request(self):
        self.pair();identity=self.store.console_id
        self.manager.operation({'operation':'remove','id':identity})
        write_json(self.store.root/'window.json',{'authorization':'ABCDEFGHIJKL','expires':1000})
        start=self.begin()
        self.assertNotIn('change',self.manager.window)
        with self.assertRaises(ValueError):self.manager.operation({'operation':'remove','id':identity})
        self.manager.confirm(start['session'],self.matrix.pin)
        self.assertTrue(self.manager.inspect()['consoles'])

    def test_reads_do_not_wait_for_reconcile_lock(self):
        import threading
        self.pair()
        held, release = threading.Event(), threading.Event()
        def hold():
            with self.manager.lock:
                held.set(); release.wait(5)
        worker = threading.Thread(target=hold); worker.start(); held.wait(5)
        try:
            self.assertEqual(len(self.manager.inspect()['consoles']), 1)
            self.assertEqual(len(self.manager.routing({'operation':'targets'})['targets']), 1)
        finally:
            release.set(); worker.join()

    def test_router_check_waits_for_console_input_test(self):
        self.pair();identity=self.store.console_id
        seen = {}
        class Peer:
            def __init__(peer, host, pin=None): pass
            def request(peer, path, payload=None, token=None, timeout=10):
                seen.update(payload=payload, timeout=timeout); return {}
        self.manager.peer = Peer
        self.manager.routing({'operation':'check','console_id':identity,'watch_ms':10000})
        self.assertEqual(seen['payload']['watch_ms'], 10000)
        self.assertGreaterEqual(seen['timeout'], 20)
        self.manager.routing({'operation':'read','console_id':identity})
        self.assertEqual(seen['timeout'], 10)

    def test_legacy_aliases_use_identity_and_both_credentials(self):
        tokens = {'virtualglove': 'existing-glove-credential', 'rob_vision': 'existing-buddy-credential'}
        for app, token in tokens.items():
            Path(self.store.adapters[app]['token_file']).write_text(token)
        request = self.adapters.request
        def legacy(app, operation, **payload):
            if operation == 'export':
                if app == 'virtualglove':
                    return {'config': {'receiver':'console.local', 'platform':'retropie', 'token':tokens[app]}}
                return {'records':[{'host':'192.168.1.10','platform':'retropie','id':'b'*32,'token':tokens[app]}]}
            return request(app, operation, **payload)
        self.adapters.request = legacy
        self.manager.import_legacy()
        self.assertEqual(len(self.manager.document['consoles']), 1)
        self.assertEqual(set(self.store.connection['apps']), set(tokens))
        self.assertEqual(self.manager.inspect()['conflicts'], [])


if __name__=='__main__':unittest.main()
