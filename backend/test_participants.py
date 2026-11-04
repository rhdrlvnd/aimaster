import unittest
from backend.test_features import FeatureTests
from backend import google_tasks
from backend.participants import is_successor


class MultipleSuccessorsTests(unittest.TestCase):
    setUp = FeatureTests.setUp
    tearDown = FeatureTests.tearDown
    login = FeatureTests.login
    state = FeatureTests.state
    features = FeatureTests.features
    post = FeatureTests.post
    draft = FeatureTests.draft
    confirm = FeatureTests.confirm

    def update_people(self, names):
        state = self.state()
        return self.client.put(self.prefix, json={
            **state['handover'], 'revision': state['revision'], 'successors': names,
        })

    def test_create_and_edit_multiple(self):
        body = dict(name='공동 인수', scope='운영', owner='김개발',
                    successors=['이후임', '박인사'], start_date='2026-10-01', end_date='2026-12-31')
        created = self.client.post('/api/handovers', json=body)
        self.assertEqual(created.status_code, 201, created.text)
        self.assertEqual(created.json()['successor_ids'], ['demo-next', 'demo-hr'])
        self.assertEqual(created.json()['successor'], '이후임, 박인사')
        self.confirm()
        before = self.features()['schedule']
        result = self.update_people(['이후임', '박인사'])
        self.assertEqual(result.status_code, 200, result.text)
        self.assertEqual(self.features()['schedule']['confirmed'], before['confirmed'])
        self.assertTrue(self.features()['schedule_current'])

    def test_all_successors_share_progress_but_cannot_manage(self):
        self.confirm()
        self.assertEqual(self.update_people(['이후임', '박인사']).status_code, 200)
        self.login('demo-next')
        self.assertEqual(self.post('/progress', item_ids=['a'], status='done').status_code, 200)
        self.login('demo-hr')
        self.assertEqual(self.features()['progress']['a']['status'], 'done')
        self.assertEqual(self.post('/progress', item_ids=['b'], status='done').status_code, 200)
        self.assertEqual(self.post('/questions', content='운영 절차 확인').status_code, 200)
        google_tasks.check_state({**self.state(), 'schedule':self.features()['schedule']}, 'demo-hr')
        self.assertEqual(self.post('/approve').status_code, 403)
        self.assertEqual(self.post('/sample').status_code, 403)
        self.assertEqual(self.update_people(['박인사']).status_code, 403)
        self.login('demo-next')
        self.assertEqual(self.features()['progress']['b']['status'], 'done')
        self.assertEqual(self.features()['progress']['b']['user_id'], 'demo-hr')
        self.assertEqual(self.post('/progress', item_ids=['a'], status='todo').status_code, 409)

    def test_removal_revokes_access_and_preserves_shared_work(self):
        self.confirm()
        self.update_people(['이후임', '박인사'])
        self.login('demo-hr')
        self.post('/progress', item_ids=['a'], status='done')
        self.login('demo-dev')
        self.assertEqual(self.update_people(['이후임']).status_code, 200)
        self.assertEqual(self.features()['progress']['a']['status'], 'done')
        self.login('demo-hr')
        self.assertEqual(self.client.get(self.prefix+'/workspace').status_code, 403)
        self.assertEqual(self.client.get(self.prefix+'/features').status_code, 403)
        self.assertEqual(self.client.post(self.prefix+'/progress', json={'revision':0, 'item_ids':['a'], 'status':'todo'}).status_code, 403)

    def test_invalid_people_and_legacy_membership(self):
        for names in ([], [''], ['없는 사용자'], ['이후임', '이후임'], ['김개발']):
            with self.subTest(names=names):
                self.assertEqual(self.update_people(names).status_code, 422)
        self.assertTrue(is_successor({'handover':{'successor_id':'demo-next'}}, 'demo-next'))
        self.assertFalse(is_successor({'handover':{'successor_id':'demo-next','successor_ids':['demo-hr']}}, 'demo-next'))
        self.login('demo-finance')
        self.assertEqual(self.client.get(self.prefix+'/features').status_code, 403)
