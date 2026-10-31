import csv
import io
import json
import os
import tempfile
import unittest
import urllib.error
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch
from cmo.agent import AgentError
from cmo.service import Service, InputError
from cmo.store import Store


class ServiceTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.env = patch.dict(os.environ, {'DEEPSEEK_API_KEY': '', 'CMO_LLM_API_KEY': '', 'CMO_DAILY_GENERATION_LIMIT': '100', 'CMO_LLM_PROVIDER': 'deepseek'})
        self.env.start()
        self.path = Path(self.directory.name) / 'db.sqlite3'
        self.s = Service(Store(self.path))

    def tearDown(self):
        self.env.stop()
        self.directory.cleanup()

    def asset(self):
        return self.s.create_asset({'channel': 'LinkedIn', 'brief': 'Explain the value of consistent marketing.'})

    def csv(self, rows):
        out = io.StringIO()
        w = csv.writer(out)
        w.writerow(['date','channel','campaign','spend','impressions','clicks','leads','revenue'])
        w.writerows(rows)
        return {'csv': out.getvalue()}

    def test_standard_deepseek_key_selects_live_mode(self):
        with patch.dict(os.environ, {'DEEPSEEK_API_KEY': 'dummy-deepseek-key'}):
            service = Service(Store(self.path))
        self.assertEqual(service.agent.key, 'dummy-deepseek-key')
        self.assertEqual(service.agent.mode, 'deepseek')
        self.assertEqual(service.agent.model, 'deepseek-chat')

    def test_generic_key_override_has_precedence(self):
        with patch.dict(os.environ, {'DEEPSEEK_API_KEY': 'dummy-provider-key', 'CMO_LLM_API_KEY': 'dummy-override-key'}):
            service = Service(Store(self.path))
        self.assertEqual(service.agent.key, 'dummy-override-key')

    def test_openai_does_not_reuse_deepseek_key(self):
        with patch.dict(os.environ, {'DEEPSEEK_API_KEY': 'dummy-provider-key', 'CMO_LLM_PROVIDER': 'openai'}):
            service = Service(Store(self.path))
        self.assertEqual(service.agent.key, '')
        self.assertEqual(service.agent.mode, 'local')

    def test_key_is_not_exposed_in_workspace_state(self):
        with patch.dict(os.environ, {'DEEPSEEK_API_KEY': 'dummy-provider-key'}):
            service = Service(Store(self.path))
        self.assertNotIn('dummy-provider-key', json.dumps(service.state()))

    def test_workspace_starts_without_fake_metrics(self):
        state = self.s.state()
        self.assertEqual(state['analytics']['totals']['leads'], 0)
        self.assertIsNone(state['analytics']['totals']['cpl'])
        self.assertEqual(state['assets'], [])

    def test_brand_persists_across_process_instances(self):
        b = {**self.s.store.brand(), 'name': 'Acme', 'monthly_budget': 90}
        self.s.save_brand(b)
        other = Service(Store(self.path))
        self.assertEqual(other.store.brand()['name'], 'Acme')
        self.assertIn('Acme', other.create_asset({'channel':'Email','brief':'A useful email.'})['body'])

    def test_invalid_brand_url_budget_and_empty_name(self):
        for change in ({'name':''}, {'monthly_budget':float('nan')}, {'website':'javascript:alert(1)'}, {'monthly_budget':-1}):
            with self.subTest(change=change), self.assertRaises(InputError):
                self.s.save_brand({**self.s.store.brand(), **change})

    def test_plan_seven_dates_and_persistent_linked_draft(self):
        p = self.s.create_plan({'goal':'Get ten qualified leads', 'week_start':'2026-11-02'})
        self.assertEqual(len(p['items']), 7)
        self.assertEqual(p['items'][-1]['date'], '2026-11-08')
        data = {**p['items'][0], 'plan_id':p['id'], 'plan_index':0}
        a = self.s.create_asset(data)
        again = self.s.create_asset(data)
        self.assertEqual(a['id'], again['id'])
        self.assertEqual(len(self.s.store.list('asset')), 1)

    def test_bad_date_and_channel(self):
        with self.assertRaises(InputError):
            self.s.create_plan({'goal':'grow', 'week_start':'2026-02-30'})
        with self.assertRaises(InputError):
            self.s.create_asset({'channel':'Unknown', 'brief':'x'})

    def test_approval_edit_and_stale_revision(self):
        a = self.asset()
        a = self.s.asset_action(a['id'], 'approve', {'revision':a['revision']})
        self.assertEqual(a['status'], 'Approved')
        self.assertIn(a['title'], self.s.export('assets'))
        old_revision = a['revision']
        a = self.s.asset_action(a['id'], 'save', {'revision':a['revision'], 'title':a['title'], 'body':a['body']+'\nEdited.'})
        self.assertEqual(a['status'], 'Draft')
        self.assertNotIn(a['title'], self.s.export('assets'))
        with self.assertRaises(InputError):
            self.s.asset_action(a['id'], 'approve', {'revision':old_revision})

    def test_brand_update_invalidates_export_approval(self):
        a = self.asset()
        self.s.asset_action(a['id'], 'approve', {'revision':a['revision']})
        self.s.save_brand({**self.s.store.brand(), 'voice':'Warm and direct'})
        self.assertNotIn(a['title'], self.s.export('assets'))

    def test_banned_words_block_approval_case_insensitively(self):
        a = self.asset()
        a = self.s.asset_action(a['id'],'save',{'revision':a['revision'],'title':a['title'],'body':a['body']+' GUARANTEED success.'})
        with self.assertRaisesRegex(InputError, 'restricted phrase'):
            self.s.asset_action(a['id'],'approve',{'revision':a['revision']})

    def test_variation_resets_approval(self):
        a = self.asset()
        a = self.s.asset_action(a['id'],'approve',{'revision':a['revision']})
        varied = self.s.asset_action(a['id'],'variation',{'revision':a['revision'],'instruction':'Make it concise'})
        self.assertEqual(varied['status'],'Draft')
        self.assertNotEqual(varied['body'],a['body'])

    def test_metrics_calculation_and_idempotent_upsert(self):
        today = date.today().isoformat()
        data = self.csv([[today,'LinkedIn','Launch',50,2000,100,10,250], [today,'Email','Launch',10,1000,50,5,50]])
        self.assertEqual(self.s.import_metrics(data), {'added':2,'updated':0})
        self.assertEqual(self.s.import_metrics(data), {'added':0,'updated':2})
        totals = self.s.analytics()['totals']
        self.assertEqual(totals['leads'],15)
        self.assertEqual(totals['cpl'],4)
        self.assertEqual(totals['ctr'],5)
        self.assertEqual(totals['roas'],5)

    def test_metrics_bad_row_rolls_back_whole_file(self):
        data = self.csv([[date.today().isoformat(),'LinkedIn','Good',10,100,10,1,20], [date.today().isoformat(),'Email','Bad',10,100,1,20,30]])
        with self.assertRaisesRegex(InputError,'Row 3'):
            self.s.import_metrics(data)
        self.assertEqual(self.s.store.list('metric'),[])

    def test_metrics_duplicates_future_nonfinite_and_fractional(self):
        row = [date.today().isoformat(),'LinkedIn','Test',10,100,20,2,20]
        for rows in ([row,row], [[(date.today()+timedelta(days=1)).isoformat(),*row[1:]]], [[*row[:3],'nan',*row[4:]]], [[*row[:4],100.2,*row[5:]]]):
            with self.subTest(rows=rows), self.assertRaises(InputError):
                self.s.import_metrics(self.csv(rows))

    def test_period_filter_and_lead_trend(self):
        today=date.today()
        self.s.import_metrics(self.csv([[today.isoformat(),'LinkedIn','Now',20,100,20,10,40], [(today-timedelta(days=35)).isoformat(),'LinkedIn','Before',20,100,20,5,40]]))
        a=self.s.analytics()
        self.assertEqual(a['totals']['leads'],10)
        self.assertEqual(a['previous']['leads'],5)
        self.assertIn('+100%', ' '.join(a['observations']))

    def test_csv_export_formula_safety(self):
        self.s.import_metrics(self.csv([[date.today().isoformat(),'Email','=HYPERLINK("evil")',10,100,10,1,20]]))
        result=list(csv.DictReader(io.StringIO(self.s.export('metrics'))))
        self.assertTrue(result[0]['campaign'].startswith("'="))

    def test_campaign_review_score_has_explainable_checks(self):
        b=self.s.store.brand()
        c=self.s.create_campaign({'name':'Launch','goal':'Leads','audience':b['audience'],'channel':'LinkedIn','offer':b['product'],'cta':b['cta'],'budget':50,'deadline':date.today().isoformat()})
        c=self.s.review_campaign(c['id'])
        self.assertEqual(c['review']['score'],100)
        self.assertEqual(len(c['review']['checks']),5)
        self.assertEqual(Service(Store(self.path)).store.get('campaign',c['id'])['status'],'Reviewed')

    def test_chat_saves_contextual_answer(self):
        self.s.chat({'question':'How is our performance?'})
        m=self.s.store.list('message')[0]
        self.assertIn('No performance data',m['answer'])
        self.assertEqual(m['source'],'local')

    def test_daily_quota_enforced(self):
        self.s.agent.limit=1
        self.asset()
        with self.assertRaisesRegex(AgentError,'Daily generation limit'):
            self.asset()
        self.assertEqual(self.s.agent.usage()['today'],1)

    def test_invalid_provider_schema_is_not_saved(self):
        self.s.agent.key='test-only-not-real'
        with patch.object(self.s.agent,'remote',return_value=({'items':[]},3)):
            with self.assertRaisesRegex(AgentError,'invalid response'):
                self.s.create_plan({'goal':'Leads','week_start':'2026-11-02'})
        self.assertEqual(self.s.store.list('plan'),[])
        self.assertEqual(self.s.agent.usage()['today'],1)

    def test_deepseek_adapter_context_and_token_accounting(self):
        self.s.agent.key='test-only-not-real'
        class Response:
            def __enter__(self):return self
            def __exit__(self,*args):pass
            def read(self,*args):return json.dumps({'choices':[{'message':{'content':json.dumps({'answer':'Use your saved brand positioning.'})}}],'usage':{'total_tokens':50}}).encode()
        with patch('urllib.request.urlopen',return_value=Response()) as send:
            self.s.chat({'question':'What should we do?'})
        req=send.call_args.args[0]
        self.assertEqual(req.full_url,'https://api.deepseek.com/chat/completions')
        data=json.loads(req.data)
        self.assertEqual(data['model'],'deepseek-chat')
        self.assertIn('NovaFlow AI',data['messages'][1]['content'])
        self.assertEqual(self.s.agent.usage()['tokens'],50)

    def test_provider_failure_does_not_fake_success_or_leak_secret(self):
        self.s.agent.key='test-only-not-real'
        error=urllib.error.HTTPError('https://api.deepseek.com',401,'bad',{},None)
        with patch('urllib.request.urlopen',side_effect=error):
            with self.assertRaisesRegex(AgentError,'rejected access') as caught:
                self.s.chat({'question':'hello'})
        self.assertNotIn('test-only-not-real',str(caught.exception))
        self.assertEqual(self.s.store.list('message'),[])


if __name__ == '__main__':
    unittest.main()
