import os, tempfile, sqlite3, json, unittest, asyncio, uuid
from pathlib import Path
from unittest.mock import patch
from fastapi.testclient import TestClient
base=Path(tempfile.mkdtemp(prefix='handover-test-',dir='C:/dev/aimaster/.artifact-build'))
os.environ['HANDOVER_DB']=str(base/'test.sqlite3')
from backend import app as mod
class HandoverTests(unittest.TestCase):
 def setUp(self):
  mod.DB=base/(str(uuid.uuid4())+'.sqlite3')
  self.client=TestClient(mod.app)
  self.client.post("/api/demo/session",json={"user_id":"demo-dev"})
 def create(self,name):
  r=self.client.post('/api/handovers',json=dict(name=name,scope='업무 범위',owner='김개발',successor='이후임',start_date='2026-10-19',end_date='2026-10-30'))
  self.assertEqual(r.status_code,201,r.text);return '/api/handovers/'+r.json()['id']
 def state(self,p):return self.client.get(p+'/workspace').json()
 def test_empty_validation_and_isolation(self):
  self.assertEqual(self.client.get('/api/handovers').json(),{'handovers':[]})
  a,b=self.create('A'),self.create('B')
  self.assertEqual(self.client.get('/api/workspace').status_code,404)
  self.assertEqual(self.client.get('/api/handovers/not-an-id/workspace').status_code,422)
  self.client.post(a+'/sample');sa=self.state(a)
  self.assertEqual(len(sa['documents']),1);self.assertEqual(self.state(b)['documents'],[])
  foreign=sa['documents'][0]['id']
  self.assertEqual(self.client.delete(b+'/documents/'+foreign+'?revision=0').status_code,404)
  self.assertEqual(self.client.get(b+'/documents/'+foreign+'/slides/1').status_code,404)
  item=dict(id='manual',title='검토',description='문서 확인',category='업무',priority='보통',reviewed=True,origin='manual',evidence=[])
  self.assertEqual(self.client.put(a+'/checklist',json={'revision':sa['revision'],'items':[item]}).status_code,200)
  self.assertEqual(self.state(b)['items'],[])
  self.assertEqual(self.client.post(a+'/approve',json={'revision':self.state(a)['revision']}).status_code,200)
  self.assertEqual(self.state(b)['status'],'empty')
  data=dict(name=' ',scope='업무',owner='a',successor='b',start_date='2026-10-30',end_date='2026-10-19')
  self.assertEqual(self.client.post('/api/handovers',json=data).status_code,422)
 def test_legacy_preserved_once(self):
  old=mod.initial();old['documents']=[{'id':str(uuid.uuid4()),'text':'기존 원문','name':'기존.docx'}];old['items']=[{'id':'old'}];old['revision']=12
  with sqlite3.connect(mod.DB) as db:
   db.execute('CREATE TABLE workspace (id INTEGER PRIMARY KEY,payload TEXT NOT NULL)')
   db.execute('INSERT INTO workspace VALUES (1,?)',(json.dumps(old),))
  first=self.client.get('/api/handovers').json()['handovers']
  self.assertEqual(len(first),1)
  state=self.state('/api/handovers/'+first[0]['id'])
  self.assertEqual(state['documents'],old['documents']);self.assertEqual(state['items'],old['items']);self.assertEqual(state['revision'],12)
  self.assertEqual(len(self.client.get('/api/handovers').json()['handovers']),1)
  self.assertTrue(mod.DB.with_name(mod.DB.stem+'-before-handovers.sqlite3').exists())
  with sqlite3.connect(mod.DB) as db:self.assertEqual(json.loads(db.execute('SELECT payload FROM workspace').fetchone()[0]),old)
 def test_metadata_and_revision(self):
  a=self.create('A');s=self.state(a)
  body={k:v for k,v in s['handover'].items() if k not in ['id','created_at']}
  body.update(name='수정',revision=s['revision'])
  self.assertEqual(self.client.put(a,json=body).status_code,200)
  self.assertEqual(self.state(a)['handover']['name'],'수정')
  self.assertEqual(self.client.put(a,json=body).status_code,409)
 def test_stream_context_and_cross_evidence(self):
  a,b=self.create('A'),self.create('B')
  async def prepare(doc,content,root,report):
   await asyncio.sleep(.01)
   return {'status':'ready','summary':'내용','index_id':str(uuid.uuid4()),'chunk_count':1}
  with patch.object(mod.rag,'prepare',prepare):
   result=self.client.post(a+'/documents/stream',files={'file':('a.txt','업무 문서 내용'.encode(),'text/plain')})
  self.assertIn('"done"',result.text)
  sa=self.state(a);self.assertEqual(sa['documents'][0]['rag']['status'],'ready')
  self.assertEqual(self.state(b)['documents'],[])
  item=dict(id='x',title='업무',description='설명',category='업무',priority='보통',origin='ai',evidence=[dict(document_id=sa['documents'][0]['id'],quote='업무 문서 내용')])
  self.assertEqual(self.client.put(b+'/checklist',json={'revision':0,'items':[item]}).status_code,422)
  self.client.delete(a+'/documents/'+sa['documents'][0]['id']+'?revision=0')
  self.assertEqual(len(self.state(a)['documents']),1) # stale revision cannot delete

 def test_parallel_streams_and_bulk_delete_are_isolated(self):
  import httpx
  a,b=self.create('A'),self.create('B')
  async def prepare(doc,content,root,report):
   await asyncio.sleep(.02 if doc['name']=='a.txt' else .01)
   return {'status':'ready','summary':doc['name'],'index_id':str(uuid.uuid4()),'chunk_count':1}
  async def requests():
   async with httpx.AsyncClient(transport=httpx.ASGITransport(app=mod.app),base_url='http://test', cookies={'handover_session':self.client.cookies.get('handover_session')}) as client:
    return await asyncio.gather(
     client.post(a+'/documents/stream',files={'file':('a.txt','A 업무 문서'.encode())}),
     client.post(b+'/documents/stream',files={'file':('b.txt','B 업무 문서'.encode())}))
  with patch.object(mod.rag,'prepare',prepare):
   responses=asyncio.run(requests())
  for r in responses:self.assertIn('"done"',r.text)
  sa,sb=self.state(a),self.state(b)
  self.assertEqual(sa['documents'][0]['rag']['summary'],'a.txt')
  self.assertEqual(sb['documents'][0]['rag']['summary'],'b.txt')
  with patch.object(mod.rag,'collection') as collection:
   self.assertEqual(self.client.delete(a+'/documents?revision='+str(sa['revision'])).status_code,200)
   deleted=collection.return_value.delete.call_args.kwargs['where']['index_id']['$in']
   self.assertEqual(deleted,[sa['documents'][0]['rag']['index_id']])
  self.assertEqual(self.state(a)['documents'],[])
  self.assertEqual(self.state(b),sb)

if __name__=='__main__':unittest.main()

