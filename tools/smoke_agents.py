import asyncio,json,tempfile,uuid
from pathlib import Path
from backend import app,rag,scheduling,knowledge

async def main():
 root=Path(tempfile.mkdtemp(prefix='agent-smoke-',dir=str(app.ROOT/'.artifact-build')))
 doc={'id':str(uuid.uuid4()),'name':'근태 운영 규정.txt','text':'매월 마지막 업무일에 근태 담당자는 근태 집계표를 확인한다. 누락된 출퇴근 기록은 당사자에게 확인을 요청한다. 팀장의 승인 후 집계표를 급여 담당자에게 전달한다. 승인 전에는 급여 자료로 전달하지 않는다.','slide_count':0}
 def report(stage,detail):print(stage,flush=True)
 doc['rag']=await rag.prepare(doc,app.build_content([doc]),root,report)
 original=app.DB;app.DB=root/'smoke.sqlite3'
 try:
  items=await app.generate([doc],report)
  print('checklist_items',len(items),flush=True)
  state={'handover':{'id':'test','name':'근태 인수인계','start_date':'2026-10-21','end_date':'2026-11-30'},'items':[dict(i.model_dump(),id=str(uuid.uuid4())) for i in items],'documents':[doc]}
  settings=scheduling.ScheduleSettings(start='2026-10-21',end='2026-11-30',durations={i['id']:1 for i in state['items']})
  rows=await scheduling.propose(state,settings,False,report)
  def validate(answer,chunks):
   item=app.Item(title='답변',description=answer.answer,category='근태',priority='보통',evidence=[app.Evidence(**e.model_dump()) for e in answer.evidence]);app.validate_evidence([item],[doc],True);app.validate_retrieved([item],chunks)
  answer=await knowledge.answer_question(state,{},'팀장의 승인 전 급여 담당자에게 집계표를 전달해도 되나요?',root,report,validate)
  result={'checklist':[i.model_dump() for i in items],'schedule':rows,'answer':answer}
  (root/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
  print('RESULT',root/'result.json',flush=True)
  if answer['insufficient'] or not answer['evidence']:raise RuntimeError('Grounded answer not obtained')
  print('PASS actual document, checklist writer/reviewer, schedule and QA calls',flush=True)
 finally:app.DB=original
asyncio.run(main())
