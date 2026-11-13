import unittest
from router_shared.controller_router import _wizard_systems, run_setup_wizard

class WizardSystemsTests(unittest.TestCase):
    def test_individual_edits_keep_unavailable_selection(self):
        state={'systems':[{'id':'nes','name':'NES'}, {'id':'samcoupe','name':'SAM Coupé'}]}
        answers=iter(['2','d'])
        scope, selected=_wizard_systems(state, ('systems',['nes','temporarily_missing']), lambda _: next(answers), lambda _: None)
        self.assertEqual(scope,'systems')
        self.assertEqual(selected,['nes','samcoupe','temporarily_missing'])

    def test_all_then_toggle_and_nes(self):
        state={'systems':[{'id':'nes','name':'NES'}, {'id':'samcoupe','name':'SAM Coupé'}]}
        answers=iter(['a','2','d'])
        self.assertEqual(_wizard_systems(state, ('nes',[]), lambda _: next(answers), lambda _: None), ('systems',['nes']))
        answers=iter(['n','d'])
        self.assertEqual(_wizard_systems(state, ('all',[]), lambda _: next(answers), lambda _: None)[0], 'nes')

    def test_wizard_saves_system_policy(self):
        class Store:
            def read(self):
                return {'inventory':[], 'config':{'virtualglove_player':None,'physical_scope':'nes','platform':'retropie'},
                        'systems':[{'id':'nes','name':'NES'},{'id':'samcoupe','name':'SAM Coupé'}], 'revision':'1','has_backup':False}
            def operate(self, op, data):
                self.saved=data['config']; return {'config':{'platform':'retropie','players':[]}}
        store=Store();answers=iter(['y','2','d','s','y'])
        self.assertEqual(run_setup_wizard(store, lambda _:next(answers), lambda _:None, verify_fn=lambda _:True),0)
        self.assertEqual(store.saved['physical_scope'],'systems')
        self.assertEqual(store.saved['physical_systems'],['nes','samcoupe'])
