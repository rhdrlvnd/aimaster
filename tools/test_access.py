import unittest
from fastapi.testclient import TestClient
from tools.test_handovers import mod, base
import uuid


class AccessTests(unittest.TestCase):
    def setUp(self):
        mod.DB = base / (str(uuid.uuid4())+'.sqlite3')
        self.client = TestClient(mod.app)

    def login(self, user):
        self.assertEqual(self.client.post('/api/demo/session',json={'user_id':user}).status_code,200)

    def test_participant_only_for_all_detail_routes(self):
        self.assertEqual(self.client.get('/api/handovers').status_code,401)
        self.login('demo-dev')
        r=self.client.post('/api/handovers',json=dict(name='보안 검증',scope='비공개 업무',owner='김개발',successor='이후임',start_date='2026-10-19',end_date='2026-10-30'))
        self.assertEqual(r.status_code,201,r.text)
        path='/api/handovers/'+r.json()['id']
        self.assertEqual(self.client.get(path+'/workspace').status_code,200)
        self.login('demo-hr')
        item=self.client.get('/api/handovers').json()['handovers'][0]
        self.assertFalse(item['can_access'])
        self.assertNotIn('scope',item)
        for method, suffix in [('get','/workspace'),('post','/sample'),('post','/generate'),('post','/generate/stream'),('post','/documents/stream'),('post','/documents/x/analyze/stream'),('get','/documents/x/slides/1'),('delete','/documents?revision=0'),('delete','/documents/x?revision=0'),('put','/checklist'),('post','/approve'),('post','/reopen'),('put','')]:
            response=getattr(self.client,method)(path+suffix)
            self.assertEqual(response.status_code,403,(suffix,response.text))
        self.login('demo-next')
        self.assertEqual(self.client.get(path+'/workspace').status_code,200)
        self.assertTrue(self.client.get('/api/handovers').json()['handovers'][0]['can_access'])

    def test_cannot_create_for_other_people(self):
        self.login('demo-hr')
        response=self.client.post('/api/handovers',json=dict(name='다른 사람',scope='업무',owner='김개발',successor='이후임',start_date='2026-10-19',end_date='2026-10-30'))
        self.assertEqual(response.status_code,403)

    def test_successor_read_only_and_only_after_approval(self):
        self.login('demo-dev')
        r=self.client.post('/api/handovers',json=dict(name='역할 검증',scope='업무',owner='김개발',successor='이후임',start_date='2026-10-19',end_date='2026-10-30'))
        path='/api/handovers/'+r.json()['id']
        self.client.post(path+'/sample')
        self.login('demo-next')
        state=self.client.get(path+'/workspace').json()
        self.assertFalse(state['permissions']['can_manage'])
        self.assertFalse(state['permissions']['can_view_content'])
        self.assertEqual(state['documents'],[])
        self.assertEqual(state['items'],[])
        self.assertFalse(self.client.get('/api/handovers').json()['handovers'][0]['can_manage'])
        for method,suffix in [('put',''),('post','/sample'),('post','/documents'),('post','/documents/stream'),('post','/documents/x/analyze/stream'),('delete','/documents?revision=0'),('delete','/documents/x?revision=0'),('post','/generate'),('post','/generate/stream'),('put','/checklist'),('post','/approve'),('post','/reopen')]:
            self.assertEqual(getattr(self.client,method)(path+suffix).status_code,403,suffix)
        self.assertEqual(self.client.get(path+'/documents/x/slides/1').status_code,403)
        self.login('demo-dev')
        state=self.client.get(path+'/workspace').json()
        self.assertTrue(state['documents'])
        item=dict(id='item',title='인수할 업무',description='운영 절차 확인',category='운영',priority='보통',origin='manual',reviewed=True,evidence=[])
        self.assertEqual(self.client.put(path+'/checklist',json={'revision':state['revision'],'items':[item]}).status_code,200)
        state=self.client.get(path+'/workspace').json()
        self.assertEqual(self.client.post(path+'/approve',json={'revision':state['revision']}).status_code,200)
        self.login('demo-next')
        state=self.client.get(path+'/workspace').json()
        self.assertTrue(state['permissions']['can_view_content'])
        self.assertEqual(state['items'][0]['title'],'인수할 업무')
        self.assertTrue(state['documents'])
        self.assertEqual(self.client.post(path+'/reopen').status_code,403)
        self.login('demo-dev')
        self.assertEqual(self.client.post(path+'/reopen',json={'revision':state['revision']}).status_code,200)
        self.login('demo-next')
        self.assertFalse(self.client.get(path+'/workspace').json()['permissions']['can_view_content'])
