import asyncio
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch
from backend.test_support import ScopedTestClient
from backend import app as app, rag

class RagTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.db=patch.object(app,'DB',Path(self.temp.name)/'test.sqlite3');self.db.start()
        self.client=ScopedTestClient(app)
        self.summary=patch.object(rag,'summarize',AsyncMock(return_value={'summary':'일일 점검 업무','slides':[]}));self.summary.start()
        async def embed(texts):return [[1.0,0.0,0.0] for _ in texts]
        self.embedding=patch.object(rag,'embed',embed);self.embedding.start()
    def tearDown(self):
        self.client.close();self.embedding.stop();self.summary.stop();self.db.stop();self.temp.cleanup()
    def upload(self):
        r=self.client.post('/api/documents/stream',files={'file':('manual.txt','매일 오전 9시에 주문 수집 결과를 확인한다.\n오류 시 운영 담당자에게 알린다.'.encode())})
        events=[app.json.loads(line) for line in r.text.splitlines()]
        self.assertEqual(events[-1]['stage'],'done',events)
        return self.client.get('/api/workspace').json(),events
    def test_full_pipeline_retrieval_and_delete(self):
        state,events=self.upload()
        self.assertEqual([e['stage'] for e in events],['receive','extract','save','summarize','chunk','embed','store','done'])
        doc=state['documents'][0]
        self.assertEqual(doc['rag']['status'],'ready')
        chunks=asyncio.run(rag.retrieve(state['documents'],app.DB.parent,lambda *args:None))
        self.assertTrue(chunks)
        self.assertEqual(chunks[0]['text'],doc['text'])
        self.assertEqual(chunks[0]['document_id'],doc['id'])
        r=self.client.delete(f"/api/documents/{doc['id']}?revision={state['revision']}")
        self.assertEqual(r.status_code,200)
        self.assertEqual(rag.collection(app.DB.parent).count(),0)
    def test_embedding_failure_preserves_document_and_retry(self):
        with patch.object(rag,'embed',AsyncMock(side_effect=app.HTTPException(502,'임베딩 실패'))):
            r=self.client.post('/api/documents/stream',files={'file':('manual.txt','원문 보존'.encode())})
        self.assertEqual(app.json.loads(r.text.splitlines()[-1])['stage'],'error')
        state=self.client.get('/api/workspace').json();doc=state['documents'][0]
        self.assertEqual(doc['text'],'원문 보존');self.assertEqual(doc['rag']['status'],'failed')
        r=self.client.post(f"/api/documents/{doc['id']}/analyze/stream",json={'revision':state['revision']})
        self.assertEqual(app.json.loads(r.text.splitlines()[-1])['stage'],'done')
        self.assertEqual(len(self.client.get('/api/workspace').json()['documents']),1)
    def test_reindex_replaces_vectors_without_duplicates(self):
        state,_=self.upload();doc=state['documents'][0]
        r=self.client.post(f"/api/documents/{doc['id']}/analyze/stream",json={'revision':state['revision']})
        self.assertEqual(app.json.loads(r.text.splitlines()[-1])['stage'],'done')
        self.assertEqual(rag.collection(app.DB.parent).count(),doc['rag']['chunk_count'])
        self.assertEqual(rag.collection(app.DB.parent).get(where={'index_id':doc['rag']['index_id']})['ids'],[])
    def test_failed_reindex_keeps_active_index(self):
        state,_=self.upload();doc=state['documents'][0]
        with patch.object(rag,'embed',AsyncMock(side_effect=app.HTTPException(502,'임베딩 실패'))):
            r=self.client.post(f"/api/documents/{doc['id']}/analyze/stream",json={'revision':state['revision']})
        self.assertEqual(app.json.loads(r.text.splitlines()[-1])['stage'],'error')
        current=self.client.get('/api/workspace').json()['documents'][0]
        self.assertEqual(current['rag'],doc['rag'])
        self.assertEqual(rag.collection(app.DB.parent).count(),doc['rag']['chunk_count'])

    def test_missing_index_blocks_retrieval(self):
        state,_=self.upload();doc=state['documents'][0]
        rag.delete_index(app.DB.parent,doc['rag']['index_id'])
        with self.assertRaises(app.HTTPException):asyncio.run(rag.retrieve(state['documents'],app.DB.parent,lambda *args:None))

    def test_bulk_delete_clears_vectors_slides_and_keeps_checklist(self):
        state,_=self.upload();doc=state['documents'][0]
        folder=app.DB.parent/'slides'/doc['id'];folder.mkdir(parents=True);(folder/'1.png').write_bytes(b'image')
        state['items']=[{'id':'item','title':'업무','description':'확인','category':'운영','priority':'보통','origin':'ai','reviewed':True,'evidence':[{'document_id':doc['id'],'quote':'매일'}]}]
        app.write_state(state)
        response=self.client.delete(f"/api/documents?revision={state['revision']}")
        self.assertEqual(response.status_code,200)
        result=self.client.get('/api/workspace').json()
        self.assertEqual(result['documents'],[]);self.assertEqual(result['status'],'stale')
        self.assertEqual(result['items'][0]['title'],'업무');self.assertEqual(result['items'][0]['evidence'],[])
        self.assertFalse(result['items'][0]['reviewed']);self.assertFalse(folder.exists())
        self.assertEqual(rag.collection(app.DB.parent).count(),0)

    def test_bulk_delete_rejects_conflict_locked_and_running(self):
        state,_=self.upload()
        self.assertEqual(self.client.delete('/api/documents?revision=0').status_code,409)
        app.INDEXING.add(state['documents'][0]['id'])
        try:self.assertEqual(self.client.delete(f"/api/documents?revision={state['revision']}").status_code,409)
        finally:app.INDEXING.clear()
        state['status']='approved';app.write_state(state)
        self.assertEqual(self.client.delete(f"/api/documents?revision={state['revision']}").status_code,409)
        self.assertEqual(len(self.client.get('/api/workspace').json()['documents']),1)

    def test_chunk_offsets_cover_original(self):
        text=('항목별 원문을 보존합니다.\n'*400)
        chunks=rag.split_text(text)
        covered=set()
        for c in chunks:
            self.assertEqual(c['text'],text[c['start']:c['end']]);self.assertLessEqual(len(c['text']),1200)
            covered.update(range(c['start'],c['end']))
        self.assertEqual(len(covered),len(text))
    def test_wrong_retrieved_reference_rejected(self):
        item=app.Item(title='업무',description='확인',category='운영',priority='보통',evidence=[app.Evidence(document_id='a',chunk_id='c',quote='없는 문장')])
        with self.assertRaises(ValueError):app.validate_retrieved([item],[{'chunk_id':'c','document_id':'a','kind':'text','text':'실제 원문'}])
    def test_unindexed_document_cannot_generate(self):
        with self.assertRaises(app.HTTPException):asyncio.run(rag.retrieve([{'id':'old','text':'old'}],app.DB.parent,lambda *args:None))
