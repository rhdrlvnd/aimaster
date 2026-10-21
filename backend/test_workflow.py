import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from backend.test_support import ScopedTestClient
from backend import app as module


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.original_db = module.DB
        module.DB = Path(self.temp.name) / 'test.sqlite3'
        self.client = ScopedTestClient(module)
        async def indexed(document_id, report):
            report('done','분석 완료')
        self.index_patch=patch.object(module,'index_document',indexed)
        self.index_patch.start()

    def tearDown(self):
        self.index_patch.stop()
        self.client.close()
        module.DB = self.original_db
        self.temp.cleanup()

    def state(self):
        return self.client.get('/api/workspace').json()

    def seed(self):
        self.assertEqual(self.client.post('/api/sample').status_code, 200)
        state = self.state()
        item = module.Item(title='주문 수집 확인', description='전날 수집 결과를 확인한다.', category='운영', priority='높음',
            evidence=[module.Evidence(document_id=state['documents'][0]['id'], quote='매일 오전 9시에 주문 운영 화면에서 전날 주문 수집 결과를 확인한다.')])
        with patch.object(module, 'generate', AsyncMock(return_value=[item])):
            result = self.client.post('/api/generate', json={'revision': state['revision']})
        self.assertEqual(result.status_code, 200)
        return self.state()

    def test_document_stream_success_and_duplicate(self):
        response = self.client.post('/api/documents/stream', files={'file':('guide.txt','매일 점검한다.'.encode())})
        events = [module.json.loads(line) for line in response.text.splitlines()]
        self.assertEqual([e['stage'] for e in events], ['receive','extract','save','done'])
        self.assertEqual(len(self.state()['documents']), 1)
        response = self.client.post('/api/documents/stream', files={'file':('guide.txt','매일 점검한다.'.encode())})
        events = [module.json.loads(line) for line in response.text.splitlines()]
        self.assertEqual(events[-1]['stage'], 'error')
        self.assertEqual(len(self.state()['documents']), 1)

    def test_document_stream_extract_failure(self):
        response = self.client.post('/api/documents/stream', files={'file':('broken.docx',b'broken')})
        events = [module.json.loads(line) for line in response.text.splitlines()]
        self.assertEqual([e['stage'] for e in events], ['receive','extract','error'])
        self.assertEqual(self.state()['documents'], [])

    def test_document_stream_ppt_stage(self):
        with patch.object(module, 'extract', return_value=('슬라이드 내용', [])), patch.object(module, 'render_slides', return_value=3):
            response = self.client.post('/api/documents/stream', files={'file':('slides.pptx',b'mocked ppt')})
        events = [module.json.loads(line) for line in response.text.splitlines()]
        self.assertEqual([e['stage'] for e in events], ['receive','extract','render','save','done'])
        self.assertIn('3장', events[-2]['detail'])

    def test_stream_reports_success_and_persists(self):
        self.client.post('/api/sample')
        state = self.state()
        async def fake(documents, report):
            report('prepare', 'ready')
            report('analyze', 'waiting')
            report('validate', 'checked')
            return []
        with patch.object(module, 'generate', fake):
            response = self.client.post('/api/generate/stream', json={'revision':state['revision']})
        events = [module.json.loads(line) for line in response.text.splitlines()]
        self.assertEqual([e['stage'] for e in events], ['prepare','analyze','validate','validate','save','done'])
        self.assertEqual(self.state()['status'], 'review')

    def test_stream_failure_does_not_overwrite(self):
        state = self.seed()
        state.update(schedule={'draft': {'rows': []}, 'confirmed': [{'item_id': 'old'}]}, progress={'old': {'status': 'done'}}, signature={'name': 'owner'})
        module.write_state(state)
        with patch.object(module, 'generate', AsyncMock(side_effect=module.HTTPException(504, 'timeout'))):
            response = self.client.post('/api/generate/stream', json={'revision':state['revision']})
        self.assertEqual(module.json.loads(response.text)['stage'], 'error')
        self.assertEqual(self.state()['items'], state['items'])
        for key in ('schedule', 'progress', 'signature'):
            self.assertEqual(module.read_state()[key], state[key])

    def test_regeneration_clears_old_schedule_after_success(self):
        state = self.seed()
        state.update(schedule={'draft': {'rows': []}, 'confirmed': [{'item_id': 'old'}]}, progress={'old': {'status': 'done'}}, signature={'name': 'owner'})
        module.write_state(state)
        item = module.Item(title='새 업무', description='업무 확인', category='운영', priority='보통', evidence=[])
        with patch.object(module, 'generate', AsyncMock(return_value=[item])):
            response = self.client.post('/api/generate/stream', json={'revision':state['revision']})
        self.assertEqual(module.json.loads(response.text.splitlines()[-1])['stage'], 'done')
        for key in ('schedule', 'progress', 'signature'):
            self.assertNotIn(key, module.read_state())

    def test_review_approval_reopen_and_persistence(self):
        state = self.seed()
        self.assertEqual(self.client.post('/api/approve', json={'revision':state['revision']}).status_code,422)
        state['items'][0]['reviewed'] = True
        self.assertEqual(self.client.put('/api/checklist', json={'revision':state['revision'],'items':state['items']}).status_code,200)
        state = self.state()
        self.assertEqual(self.client.post('/api/approve',json={'revision':state['revision']}).status_code,200)
        approved = self.state()
        self.assertEqual(approved['status'],'approved')
        self.assertEqual(self.client.post('/api/sample').status_code,409)
        self.assertEqual(self.client.put('/api/checklist',json={'revision':approved['revision'],'items':approved['items']}).status_code,409)
        self.assertEqual(module.read_state()['status'],'approved')
        self.assertEqual(self.client.post('/api/reopen',json={'revision':approved['revision']}).status_code,200)
        self.assertFalse(self.state()['items'][0]['reviewed'])

    def test_document_change_blocks_approval(self):
        state = self.seed()
        self.assertEqual(self.client.post('/api/documents',files={'file':('more.md','추가 업무: 매월 보고서를 작성한다.'.encode(),'text/plain')}).status_code,200)
        state = self.state()
        self.assertEqual(state['status'],'stale')
        state['items'][0]['reviewed']=True
        self.client.put('/api/checklist',json={'revision':state['revision'],'items':state['items']})
        state = self.state()
        self.assertEqual(self.client.post('/api/approve',json={'revision':state['revision']}).status_code,422)

    def test_invalid_evidence_and_duplicate_ids_rejected(self):
        state = self.seed()
        state['items'][0]['evidence'][0]['quote']='원문에 없는 내용'
        response = self.client.put('/api/checklist',json={'revision':state['revision'],'items':state['items']})
        self.assertEqual(response.status_code,422)
        state = self.state()
        self.assertEqual(self.client.put('/api/checklist',json={'revision':state['revision'],'items':state['items']*2}).status_code,422)

    def test_ai_items_without_evidence_cannot_save_or_approve(self):
        state = self.seed()
        state['items'][0]['evidence'] = []
        state['items'][0]['reviewed'] = True
        response = self.client.put('/api/checklist',json={'revision':state['revision'],'items':state['items']})
        self.assertEqual(response.status_code,422)
        module.write_state(state)
        response = self.client.post('/api/approve',json={'revision':state['revision']})
        self.assertEqual(response.status_code,422)

    def test_upload_limits_and_duplicates(self):
        self.assertEqual(self.client.post('/api/documents',files={'file':('a.pdf',b'data','application/pdf')}).status_code,422)
        self.assertEqual(self.client.post('/api/documents',files={'file':('a.txt',b'','text/plain')}).status_code,422)
        self.assertEqual(self.client.post('/api/documents',files={'file':('a.txt',b'x'*512001,'text/plain')}).status_code,413)
        self.client.post('/api/sample')
        self.assertEqual(self.client.post('/api/sample').status_code,409)

    def test_stale_revision_preserves_newer_changes(self):
        state = self.seed()
        old_revision=state['revision']
        state['items'][0]['title']='수정된 업무'
        self.client.put('/api/checklist',json={'revision':old_revision,'items':state['items']})
        self.assertEqual(self.client.put('/api/checklist',json={'revision':old_revision,'items':[]}).status_code,409)
        self.assertEqual(self.state()['items'][0]['title'],'수정된 업무')

    def test_api_failure_never_creates_fake_items(self):
        self.client.post('/api/sample')
        state=self.state()
        with patch.dict(module.os.environ, {'LLM_API_KEY':''}):
            self.assertEqual(self.client.post('/api/generate',json={'revision':state['revision']}).status_code,503)
        self.assertEqual(self.state()['items'],[])


if __name__=='__main__':
    unittest.main()
