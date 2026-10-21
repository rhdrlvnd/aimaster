import asyncio, json, tempfile, unittest, uuid
from pathlib import Path
from unittest.mock import patch, AsyncMock, MagicMock
from io import BytesIO
from fastapi.testclient import TestClient
from docx import Document
from backend import app as m, scheduling, knowledge, calendar_api

class FeatureTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.old=m.DB;m.DB=Path(self.temp.name)/'test.sqlite3'
  self.client=TestClient(m.app);self.login('demo-dev')
  body=dict(name='업무 인수인계',scope='월 마감',owner='김개발',successor='이후임',start_date='2026-10-01',end_date='2026-12-31')
  r=self.client.post('/api/handovers',json=body);self.prefix='/api/handovers/'+r.json()['id']
  self.client.post(self.prefix+'/sample')
  self.items=[dict(id=k,title=t,description='업무 절차를 확인한다.',category='운영',priority='보통',origin='manual',reviewed=True,evidence=[]) for k,t in [('a','자료 확인'),('b','월 마감')]]
  self.items[1]['dependencies']=['a']
  self.client.put(self.prefix+'/checklist',json={'revision':self.state()['revision'],'items':self.items})
  self.client.post(self.prefix+'/approve',json={'revision':self.state()['revision']})
  self.settings=dict(start='2026-10-26',end='2026-11-06',weekends=False,holidays=['2026-10-27'],durations={'a':1,'b':2},dependencies={'b':['a']})
 def tearDown(self):self.client.close();m.DB=self.old;self.temp.cleanup()
 def login(self,user):self.client.post('/api/demo/session',json={'user_id':user}).raise_for_status()
 def state(self):return self.client.get(self.prefix+'/workspace').json()
 def features(self):return self.client.get(self.prefix+'/features').json()
 def post(self,path,**body):return self.client.post(self.prefix+path,json={'revision':self.state()['revision'],**body})
 def draft(self):
  with patch.object(scheduling,'json_call',AsyncMock(return_value={'items':[{'item_id':'b','reason':'마감'},{'item_id':'a','reason':'먼저 확인'}]})):
   r=self.post('/schedule/generate/stream',settings=self.settings)
  self.assertEqual(json.loads(r.text.splitlines()[-1])['stage'],'done',r.text)
  return self.features()['schedule']['draft']['rows']
 def confirm(self):
  rows=self.draft();r=self.post('/schedule/confirm',rows=rows);self.assertEqual(r.status_code,200,r.text);return rows
 def test_schedule_validation_progress_and_export(self):
  rows=self.confirm();by={r['item_id']:r for r in rows}
  self.assertEqual(by['a']['start'],'2026-10-26');self.assertEqual(by['b']['start'],'2026-10-28');self.assertEqual(by['b']['end'],'2026-10-29')
  self.assertEqual(self.client.get(self.prefix+'/export').status_code,409)
  self.assertEqual(self.post('/signature',name='다른사람',consent=True).status_code,422)
  self.assertEqual(self.post('/signature',name='김개발',consent=True).status_code,200)
  r=self.client.get(self.prefix+'/export');self.assertEqual(r.status_code,200)
  text='\n'.join(p.text for p in Document(BytesIO(r.content)).paragraphs)
  self.assertIn('월 마감',text);self.assertIn('서명자: 김개발',text)
  self.login('demo-next')
  self.assertEqual(self.post('/progress',item_ids=['b'],status='done').status_code,409)
  self.assertEqual(self.post('/progress',item_ids=['a'],status='done').status_code,200)
  self.assertEqual(self.post('/progress',item_ids=['b'],status='done').status_code,200)
  self.assertEqual(self.features()['progress']['b']['status'],'done')
  self.assertEqual(self.post('/progress',item_ids=['a'],status='todo').status_code,409)
  self.assertEqual(self.client.get(self.prefix+'/export').status_code,403)
 def test_role_boundaries_and_question_board(self):
  self.assertEqual(self.post('/questions',content='질문').status_code,403)
  self.login('demo-next')
  self.assertEqual(self.post('/schedule/generate/stream',settings=self.settings).status_code,403)
  self.assertEqual(self.post('/signature',name='이후임',consent=True).status_code,403)
  self.assertEqual(self.post('/questions',content='마감 기준이 무엇인가요?').status_code,200)
  q=self.features()['questions'][0]
  self.assertEqual(self.post('/questions/'+q['id']+'/answer',content='답변').status_code,403)
  self.login('demo-dev');self.assertEqual(self.post('/questions/'+q['id']+'/answer',content='매월 말 확인합니다.').status_code,200)
  self.login('demo-next');self.assertEqual(self.features()['questions'][0]['answer'],'매월 말 확인합니다.')
  self.login('demo-hr');self.assertEqual(self.client.get(self.prefix+'/features').status_code,403)
 def test_invalid_schedule_and_revision(self):
  settings=scheduling.ScheduleSettings(**{**self.settings,'dependencies':{'a':['b'],'b':['a']}})
  with self.assertRaises(m.HTTPException):scheduling.validate_settings({'items':self.items,'handover':self.state()['handover']},settings)
  rows=self.draft();rows[0]['end']='2027-01-01'
  self.assertEqual(self.post('/schedule/confirm',rows=rows).status_code,422)
  self.assertEqual(self.client.post(self.prefix+'/schedule/confirm',json={'revision':0,'rows':rows}).status_code,409)
 def test_schedule_capacity_fails_before_ai(self):
  settings={**self.settings,'end':'2026-10-28'}
  with patch.object(scheduling,'json_call',AsyncMock()) as ai:
   r=self.post('/schedule/generate/stream',settings=settings)
  self.assertIn('3업무일',r.text)
  self.assertIn('2업무일',r.text)
  ai.assert_not_awaited()
  self.assertFalse(self.features()['schedule'].get('draft'))
 def test_cycle_error_identifies_actual_tasks(self):
  settings=scheduling.ScheduleSettings(**{**self.settings,'dependencies':{'a':['b'],'b':['a']}})
  with self.assertRaises(m.HTTPException) as caught:
   scheduling.validate_settings({'items':self.items,'handover':self.state()['handover']},settings)
  self.assertIn('자료 확인',caught.exception.detail)
  self.assertIn('월 마감',caught.exception.detail)
  self.assertIn(' → ',caught.exception.detail)
 def test_hour_schedule_places_dependent_tasks_same_day(self):
  self.settings.update(unit='hour',daily_hours=4,day_start=9)
  rows=self.draft();by={r['item_id']:r for r in rows}
  self.assertEqual(by['a']['start'],by['b']['start'])
  self.assertEqual(by['a']['end_time'],'10:00:00')
  self.assertEqual(by['b']['start_time'],'10:00:00')
  self.assertEqual(by['b']['end_time'],'12:00:00')
  rows[1]['start_time']='09:00:00'
  self.assertEqual(self.post('/schedule/confirm',rows=rows).status_code,422)
 def test_hour_schedule_skips_holidays_and_keeps_duration(self):
  self.settings.update(unit='hour',daily_hours=2,day_start=9)
  rows=self.draft();by={r['item_id']:r for r in rows}
  self.assertEqual(by['b']['start'],'2026-10-26')
  self.assertEqual(by['b']['end'],'2026-10-28')
  self.assertEqual(by['b']['end_time'],'10:00:00')
 def test_hour_reschedule_preserves_completed_time(self):
  self.settings.update(unit='hour',daily_hours=4,day_start=9)
  original=self.confirm()
  self.login('demo-next');self.post('/progress',item_ids=['a'],status='done');self.login('demo-dev')
  with patch.object(scheduling,'json_call',AsyncMock(return_value={'items':[{'item_id':'b','reason':'후속'},{'item_id':'a','reason':'완료'}]})):
   r=self.post('/schedule/generate/stream',settings=self.settings,reschedule=True)
  self.assertEqual(json.loads(r.text.splitlines()[-1])['stage'],'done',r.text)
  rows=self.features()['schedule']['draft']['rows']
  self.assertEqual(next(r for r in rows if r['item_id']=='a'),next(r for r in original if r['item_id']=='a'))
 def test_schedule_uses_reviewed_dependencies_not_request(self):
  self.settings['dependencies']={}
  rows=self.draft();by={r['item_id']:r for r in rows}
  self.assertLess(by['a']['end'],by['b']['start'])
  self.assertEqual(self.features()['schedule']['draft']['settings']['dependencies']['b'],['a'])
 def test_dependency_suggestion_requires_editable_owner_and_preserves_items(self):
  self.assertEqual(self.post('/checklist/dependencies/stream').status_code,409)
  self.post('/reopen')
  self.login('demo-next')
  self.assertEqual(self.post('/checklist/dependencies/stream').status_code,403)
  self.login('demo-dev')
  suggested=[{**i,'dependencies':([] if i['id']=='a' else ['a']),'reviewed':False} for i in self.items]
  with patch.object(m.dependencies,'suggest',AsyncMock(return_value=suggested)):
   response=self.post('/checklist/dependencies/stream')
  self.assertEqual(json.loads(response.text.splitlines()[-1])['stage'],'done',response.text)
  self.assertEqual([i['title'] for i in self.state()['items']],[i['title'] for i in self.items])
  self.assertFalse(any(i['reviewed'] for i in self.state()['items']))
 def test_schedule_invalidated_after_checklist_change(self):
  self.confirm();self.post('/reopen')
  items=[{**i,'description':'수정한 절차','reviewed':True} for i in self.items]
  self.client.put(self.prefix+'/checklist',json={'revision':self.state()['revision'],'items':items})
  self.post('/approve');self.login('demo-next')
  self.assertFalse(self.features()['schedule_current']);self.assertEqual(self.post('/progress',item_ids=['a'],status='done').status_code,409)
 def test_conversation_isolation_and_action_confirmation(self):
  self.confirm();self.login('demo-next')
  result={'answer':'자료 확인을 완료 처리할까요?','evidence':[],'insufficient':False,'action':{'kind':'progress','item_ids':['a'],'status':'done'}}
  with patch.object(knowledge,'answer_question',AsyncMock(return_value=result)):
   r=self.post('/qa/stream',question='자료 확인 완료 처리')
  self.assertEqual(json.loads(r.text.splitlines()[-1])['stage'],'done')
  f=self.features();c=f['conversations'][0];msg=c['messages'][0]
  self.assertEqual(f['progress'],{})
  self.assertNotIn('conversations',self.state())
  self.login('demo-dev');self.assertEqual(self.features()['conversations'],[])
  self.login('demo-next');self.assertEqual(self.post('/qa/action',conversation_id=c['id'],message_id=msg['id']).status_code,200)
  self.assertEqual(self.features()['progress']['a']['status'],'done')
  self.assertEqual(self.post('/qa/action',conversation_id=c['id'],message_id=msg['id']).status_code,409)
 def test_calendar_events_without_credentials_fail_explicitly(self):
  self.confirm();self.login('demo-next')
  calendar_api.TOKENS.clear()
  self.assertEqual(self.post('/calendar/events',item_ids=['a']).status_code,409)
  with patch.dict('os.environ',{'GOOGLE_CLIENT_ID':'','GOOGLE_CLIENT_SECRET':''}):
   self.assertEqual(self.client.post('/api/calendar/connect').status_code,503)
 def test_completed_schedule_cannot_be_moved(self):
  rows=self.confirm();self.login('demo-next');self.post('/progress',item_ids=['a'],status='done');self.login('demo-dev')
  with patch.object(scheduling,'json_call',AsyncMock(return_value={'items':[{'item_id':'a','reason':'유지'},{'item_id':'b','reason':'다음'}]})):
   response=self.post('/schedule/generate/stream',settings=self.settings,reschedule=True)
  self.assertEqual(json.loads(response.text.splitlines()[-1])['stage'],'done',response.text)
  draft=self.features()['schedule']['draft']['rows'];a=next(r for r in draft if r['item_id']=='a');a['start']='2026-10-28';a['end']='2026-10-28'
  self.assertEqual(self.post('/schedule/confirm',rows=draft).status_code,422)

 def test_oauth_state_is_bound_to_session_and_single_use(self):
  from urllib.parse import urlparse, parse_qs
  with patch.dict('os.environ',{'GOOGLE_CLIENT_ID':'test-client','GOOGLE_CLIENT_SECRET':'test-secret'}):
   response=self.client.post('/api/calendar/connect')
   query=parse_qs(urlparse(response.json()['url']).query)
   self.assertEqual(query['code_challenge_method'],['S256'])
   nonce=query['state'][0]
   self.login('demo-next')
   with patch.object(calendar_api.httpx,'AsyncClient') as http:
    self.assertEqual(self.client.get('/api/calendar/callback',params={'state':nonce,'code':'unused'}).status_code,400)
    http.assert_not_called()
   self.assertEqual(self.client.get('/api/calendar/callback',params={'state':nonce,'code':'unused'}).status_code,400)

class CalendarTests(unittest.IsolatedAsyncioTestCase):
 async def test_duplicate_is_updated_and_partial_failure_reported(self):
  client=AsyncMock();client.__aenter__.return_value=client
  client.post.side_effect=[MagicMock(status_code=409),MagicMock(status_code=503)]
  client.patch.return_value=MagicMock(status_code=200)
  state={'handover':{'id':'h','name':'인수인계'},'items':[{'id':x,'title':x,'description':'설명'} for x in ['a','b']], 'schedule':{'confirmed':[{'item_id':x,'start':'2026-10-26','end':'2026-10-26'} for x in ['a','b']]}}
  with patch.object(calendar_api,'access_token',AsyncMock(return_value='test')),patch.object(calendar_api.httpx,'AsyncClient',return_value=client):
   rows=await calendar_api.sync_events({'id':'u'},state,['a','b'])
  self.assertEqual([r['status'] for r in rows],['success','failed']);client.patch.assert_awaited_once()
  self.assertEqual(client.post.call_args_list[0].kwargs['json']['end']['date'],'2026-10-27')
