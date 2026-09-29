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
