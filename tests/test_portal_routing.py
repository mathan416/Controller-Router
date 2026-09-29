import unittest
from unittest.mock import patch
from uno_portal.host import routing

class RoutingTests(unittest.TestCase):
    def state(self, *apps, active=False):
        return {'apps': {app: {'installed': True, 'game_active': active} for app in apps}}

    def test_one_and_both_product_target_lists(self):
        console = {'id':'abc','name':'RetroPie','host':'retropie.local'}
        for apps in [('virtualglove',), ('rob_vision',), ('virtualglove','rob_vision')]:
            with patch.object(routing, 'product_request', return_value={'receiver':'retropie.local','platform':'retropie','link':{'consoles':[console]}}):
                rows = routing.targets(self.state(*apps))['targets']
            self.assertEqual([row['app'] for row in rows], list(apps))
            self.assertTrue(all(set(row) == {'app','console_id','name'} for row in rows))

    def test_virtualglove_save_retains_revision_and_draft(self):
        draft={'players':[{'player':1,'sources':['id']}], 'virtualglove_player':1}
        with patch.object(routing, 'product_request', return_value={'revision':'next'}) as request:
            routing.routing({'operation':'save','app':'virtualglove','revision':'old','config':draft},self.state('virtualglove'))
        self.assertEqual(request.call_args.args[:2], ('virtualglove','/api/controller-router'))
        self.assertEqual(request.call_args.args[2]['config'],draft)
        self.assertEqual(request.call_args.args[2]['revision'],'old')

    def test_unknown_console_and_active_game_block_without_writing(self):
        with patch.object(routing, 'product_request', return_value={'link':{'consoles':[]}}) as request:
            with self.assertRaisesRegex(ValueError,'paired console'):
                routing.routing({'operation':'save','app':'rob_vision','console_id':'unknown'},self.state('rob_vision'))
            request.reset_mock()
            with self.assertRaisesRegex(ValueError,'Exit'):
                routing.routing({'operation':'save','app':'virtualglove'},self.state('virtualglove',active=True))
            request.assert_not_called()

    def test_uninstalled_and_arbitrary_actions_are_rejected(self):
        with self.assertRaises(ValueError):
            routing.routing({'operation':'save','app':'rob_vision'},self.state('virtualglove'))
        with self.assertRaises(ValueError):
            routing.routing({'operation':'command','app':'virtualglove'},self.state('virtualglove'))
