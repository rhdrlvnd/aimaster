import unittest
from datetime import date
from backend import scheduling
from backend.admin_dashboard import summarize
from backend.test_features import FeatureTests


class AdminDashboardTests(unittest.TestCase):
    setUp = FeatureTests.setUp
    tearDown = FeatureTests.tearDown
    login = FeatureTests.login
    state = FeatureTests.state
    features = FeatureTests.features
    post = FeatureTests.post
    draft = FeatureTests.draft
    confirm = FeatureTests.confirm

    def test_admin_only_and_summary_without_private_contents(self):
        self.confirm()
        self.assertEqual(self.client.get('/api/admin/dashboard').status_code, 403)
        self.login('demo-next')
        self.assertEqual(self.client.get('/api/admin/dashboard').status_code, 403)
        self.login('demo-admin')
        result = self.client.get('/api/admin/dashboard')
        self.assertEqual(result.status_code, 200, result.text)
        row = result.json()['handovers'][0]
        self.assertEqual(row['total'], 2)
        for private in ('items', 'documents', 'questions', 'conversations', 'signature', 'scope'):
            self.assertNotIn(private, row)
        workspace = self.client.get(self.prefix+'/workspace')
        self.assertEqual(workspace.status_code, 200)
        self.assertTrue(workspace.json()['permissions']['admin_read_only'])
        self.assertFalse(workspace.json()['permissions']['can_manage'])
        self.assertEqual(len(workspace.json()['items']), 2)
        self.assertEqual(self.client.get(self.prefix+'/features').status_code, 200)
        for route, payload in [('/progress', {'item_ids':['a'], 'status':'done'}), ('/questions', {'content':'관리자 질문'}), ('/sample', {}), ('/approve', {}), ('/google/tasks', {'item_ids':['a']})]:
            with self.subTest(route=route):
                self.assertEqual(self.post(route, **payload).status_code, 403)
        self.assertEqual(self.client.put(self.prefix+'/checklist', json={'revision':self.state()['revision'],'items':self.items}).status_code, 403)
        self.assertEqual(self.client.post('/api/handovers', json=dict(name='관리자 생성', scope='시험', owner='관리자', successor='이후임', start_date='2026-11-01', end_date='2026-11-30')).status_code, 422)

    def test_admin_can_read_unapproved_workspace(self):
        self.login('demo-dev')
        self.post('/reopen')
        self.login('demo-admin')
        state = self.state()
        self.assertTrue(state['permissions']['can_view_content'])
        self.assertFalse(state['permissions']['can_manage'])
        self.assertEqual(len(state['items']), 2)
        self.assertEqual(self.client.get(self.prefix+'/features').status_code, 200)

    def test_schedule_status_boundaries_and_stale_schedule(self):
        rows = self.confirm()
        state = {**self.state(), 'schedule':self.features()['schedule'], 'progress':{}}
        self.assertEqual(summarize(state, date(2026, 10, 26))['status'], 'on_track')
        late = summarize(state, date(2026, 11, 7))
        self.assertEqual(late['status'], 'delayed')
        self.assertEqual(late['overdue'], 2)
        state['progress'] = {r['item_id']:{'status':'done'} for r in rows}
        self.assertEqual(summarize(state, date(2026, 11, 7))['status'], 'complete')
        state['items'][0]['title'] = '변경된 내용'
        review = summarize(state, date(2026, 11, 7))
        self.assertEqual(review['status'], 'review')
        self.assertIsNone(review['overdue'])

    def test_no_schedule_and_deadline_today(self):
        state = self.state()
        self.assertEqual(summarize(state, date(2026, 10, 1))['status'], 'unscheduled')
        self.assertEqual(summarize(state, date(2027, 1, 1))['status'], 'delayed')
        state['handover']['end_date'] = '2026-11-02'
        state['schedule'] = {'confirmed':[{'item_id':'a','start':'2026-11-02','end':'2026-11-02'}, {'item_id':'b','start':'2026-11-02','end':'2026-11-02'}]}
        state['schedule']['fingerprint'] = scheduling.fingerprint(state)
        row = summarize(state, date(2026, 11, 2))
        self.assertEqual(row['status'], 'soon')
        self.assertEqual(row['overdue'], 0)
        self.assertEqual(row['days_remaining'], 0)
