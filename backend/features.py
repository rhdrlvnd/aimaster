"""Participant workflows. Every mutation has an explicit role and revision guard."""
import json, uuid, hashlib
from datetime import datetime
from zoneinfo import ZoneInfo
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response
from pydantic import BaseModel, Field
from typing import Literal
from backend import scheduling, knowledge, calendar_api
from backend.agents import json_call
from backend.exporting import build_docx

class Version(BaseModel): revision:int
class Proposal(Version):
    settings:scheduling.ScheduleSettings
    reschedule:bool=False
class ScheduleEdit(Version):
    rows:list[scheduling.ScheduleRow]
class ScheduleMove(ScheduleEdit):
    item_id:str
    start:str
    hour:int=Field(ge=0,le=23)
class ProgressEdit(Version):
    item_ids:list[str]=Field(min_length=1,max_length=100)
    status:Literal['todo','doing','done']
class Ask(Version):
    conversation_id:str|None=None
    question:str=Field(min_length=1,max_length=4000)
class Question(Version): content:str=Field(min_length=1,max_length=8000)
class ForwardQuestion(Question):
    conversation_id:str|None=None
    message_id:str|None=None
class ActionConfirm(Version):
    conversation_id:str
    message_id:str
class Signature(Version):
    name:str=Field(min_length=1,max_length=80)
    consent:bool
class Events(Version): item_ids:list[str]=Field(min_length=1,max_length=100)

def install(m):
    router=APIRouter()
    async def scope(handover_id:uuid.UUID,user=Depends(m.current_user)):
        m.ensure_storage();token=m.HANDOVER_ID.set(str(handover_id))
        try:
            state=m.read_state()
            if not m.participant(state,user): raise HTTPException(403,'지정된 인계자·인수자만 접근할 수 있습니다.')
            if state['handover']['owner_id']!=user['id'] and state['status']!='approved':
                raise HTTPException(403,'인계자가 확정한 뒤 사용할 수 있습니다.')
            yield
        finally:m.HANDOVER_ID.reset(token)
    def owner(state,user):
        if state['handover']['owner_id']!=user['id']: raise HTTPException(403,'인계자만 사용할 수 있습니다.')
    def successor(state,user):
        if state['handover']['successor_id']!=user['id']: raise HTTPException(403,'인수자만 사용할 수 있습니다.')
    def approved(state):
        if state['status']!='approved': raise HTTPException(409,'체크리스트를 먼저 확정해 주세요.')
    def valid_schedule(state):
        approved(state)
        schedule=state.get('schedule',{})
        if not schedule.get('confirmed') or schedule.get('fingerprint')!=scheduling.fingerprint(state):
            raise HTTPException(409,'최신 체크리스트와 기간 기준으로 일정을 확정해 주세요.')
        return schedule
    def persist_progress(state,body,user):
        successor(state,user);valid_schedule(state)
        ids={i['id'] for i in state['items']}
        if set(body.item_ids)-ids or len(set(body.item_ids))!=len(body.item_ids): raise HTTPException(422,'대상 항목을 확인해 주세요.')
        progress=state.setdefault('progress',{})
        deps=state['schedule']['settings'].get('dependencies',{})
        if body.status=='done':
            done={k for k,v in progress.items() if v['status']=='done'}|set(body.item_ids)
            if any(not set(deps.get(k,[]))<=done for k in body.item_ids): raise HTTPException(409,'선행 업무를 먼저 완료해 주세요.')
        else:
            if any(v['status']=='done' and k not in body.item_ids and set(deps.get(k,[]))&set(body.item_ids) for k,v in progress.items()):
                raise HTTPException(409,'완료된 후속 업무가 있습니다. 후속 업무의 상태를 먼저 변경해 주세요.')
        for key in body.item_ids: progress[key]={'status':body.status,'updated_at':m.now(),'user_id':user['id']}
    @router.get('/features')
    def features(user=Depends(m.current_user)):
        state=m.read_state();schedule=state.get('schedule',{})
        own=state['handover']['owner_id']==user['id']
        public={k:v for k,v in schedule.items() if k!='draft'}
        if own and schedule.get('draft'): public['draft']=schedule['draft']
        return {'revision':state['revision'],'schedule':public,'schedule_current':schedule.get('fingerprint')==scheduling.fingerprint(state),
            'draft_current':schedule.get('draft',{}).get('fingerprint')==scheduling.fingerprint(state),
            'progress':state.get('progress',{}),'questions':state.get('questions',[]),
            'conversations':[c for c in state.get('conversations',[]) if c['user_id']==user['id']],
            'signature':state.get('signature') if own else None,'calendar_results':state.get('calendar_results',{}).get(user['id'],[]),
            'calendar':calendar_api.status(user)}
    @router.post('/schedule/generate/stream')
    async def schedule_generate(body:Proposal,user=Depends(m.current_user)):
        state=m.read_state();owner(state,user);approved(state);m.check_revision(state,body.revision)
        # The schedule form edits the handover period itself. Persist only after
        # planning succeeds so a failed request preserves both period and schedule.
        state['handover'].update(start_date=str(body.settings.start),end_date=str(body.settings.end))
        previous=state.get('schedule',{})
        completed=previous.get('preserved_completed',{}) | {r['item_id']:r for r in previous.get('confirmed',[]) if state.get('progress',{}).get(r['item_id'],{}).get('status')=='done'}
        if any(r['start']<str(body.settings.start) or r['end']>str(body.settings.end) for r in completed.values()):
            raise HTTPException(422,'완료된 업무 날짜를 포함하도록 인수인계 기간을 설정해 주세요.')
        # Reviewed checklist relations are authoritative, not the schedule form.
        body.settings.dependencies={i['id']:i.get('dependencies',[]) for i in state['items']}
        async def run(report):
            rows=await scheduling.propose(state,body.settings,body.reschedule,report)
            with m.LOCK:
                current=m.read_state();owner(current,user);approved(current);m.check_revision(current,body.revision)
                previous=current.get('schedule',{})
                preserved=previous.get('preserved_completed',{}) | {r['item_id']:r for r in previous.get('confirmed',[]) if current.get('progress',{}).get(r['item_id'],{}).get('status')=='done'}
                current['handover'].update(start_date=str(body.settings.start),end_date=str(body.settings.end))
                current['schedule']={'draft':{'rows':rows,'settings':body.settings.model_dump(mode='json'),'fingerprint':scheduling.fingerprint(current),'reschedule':body.reschedule},'preserved_completed':preserved}
                current.pop('signature',None)
                m.write_state(current)
            report('done','일정 초안을 작성했습니다. 날짜와 배치 이유를 확인하고 확정해 주세요.')
        return m.progress_response(run)
    @router.post('/schedule/move')
    def schedule_move(body:ScheduleMove,user=Depends(m.current_user)):
        state=m.read_state();owner(state,user);approved(state);m.check_revision(state,body.revision)
        draft=state.get('schedule',{}).get('draft')
        if not draft or draft['fingerprint']!=scheduling.fingerprint(state):
            raise HTTPException(409,'최신 체크리스트로 일정 초안을 다시 생성해 주세요.')
        settings=scheduling.ScheduleSettings(**draft['settings'])
        if settings.unit not in ('hour','balanced'): raise HTTPException(422,'새 일정 초안을 생성해 주세요.')
        fixed=state.get('schedule',{}).get('preserved_completed',{}) | {r['item_id']:r for r in state.get('schedule',{}).get('confirmed',[]) if state.get('progress',{}).get(r['item_id'],{}).get('status')=='done'}
        if body.item_id in fixed: raise HTTPException(409,'완료된 업무는 이동할 수 없습니다.')
        from datetime import date,time
        try: target=(date.fromisoformat(body.start),body.hour)
        except ValueError: raise HTTPException(422,'올바른 날짜를 선택해 주세요.')
        if settings.unit=='balanced':
            if body.item_id not in {r.item_id for r in body.rows}: raise HTTPException(422,'업무를 찾을 수 없습니다.')
            rows=[r.model_copy(deep=True) for r in body.rows]
            for row in rows:
                if row.item_id==body.item_id:
                    row.start=row.end=target[0];row.start_time=row.end_time=None
            scheduling.validate_rows(state,settings,rows,fixed)
            return {'rows':[r.model_dump(mode='json') for r in rows]}
        slots=scheduling.hour_slots(settings)
        if target not in slots or body.item_id not in settings.durations:
            raise HTTPException(422,'인수인계 기간과 하루 가능 시간 안의 업무일로 이동해 주세요.')
        start=slots.index(target); selected=slots[start:start+settings.durations[body.item_id]]
        if len(selected)!=settings.durations[body.item_id]: raise HTTPException(422,'남은 기간에 업무 소요 시간을 배치할 수 없습니다.')
        rows=[r.model_copy(deep=True) for r in body.rows]
        for row in rows:
            if row.item_id==body.item_id:
                row.start=selected[0][0];row.start_time=time(selected[0][1])
                row.end=selected[-1][0];row.end_time=time(selected[-1][1]+1)
        scheduling.validate_rows(state,settings,rows,fixed)
        return {'rows':[r.model_dump(mode='json') for r in rows]}

    @router.post('/schedule/confirm')
    def schedule_confirm(body:ScheduleEdit,user=Depends(m.current_user)):
        with m.LOCK:
            state=m.read_state();owner(state,user);approved(state);m.check_revision(state,body.revision)
            draft=state.get('schedule',{}).get('draft')
            if not draft or draft['fingerprint']!=scheduling.fingerprint(state): raise HTTPException(409,'최신 자료로 일정 초안을 생성해 주세요.')
            fixed=state.get('schedule',{}).get('preserved_completed',{}) | {r['item_id']:r for r in state.get('schedule',{}).get('confirmed',[]) if state.get('progress',{}).get(r['item_id'],{}).get('status')=='done'}
            scheduling.validate_rows(state,scheduling.ScheduleSettings(**draft['settings']),body.rows,fixed)
            state['schedule']={'confirmed':[r.model_dump(mode='json') for r in body.rows],'settings':draft['settings'],'fingerprint':draft['fingerprint'],'confirmed_at':m.now()}
            state.pop('signature',None);m.write_state(state)
        return {'ok':True}
    @router.post('/progress')
    def progress(body:ProgressEdit,user=Depends(m.current_user)):
        with m.LOCK:
            state=m.read_state();m.check_revision(state,body.revision);persist_progress(state,body,user);m.write_state(state)
        return {'ok':True}
    @router.post('/questions')
    def question(body:ForwardQuestion,user=Depends(m.current_user)):
        with m.LOCK:
            state=m.read_state();successor(state,user);approved(state);m.check_revision(state,body.revision)
            if not body.content.strip(): raise HTTPException(422,'질문을 입력해 주세요.')
            context={}
            if body.conversation_id or body.message_id:
                conv=next((c for c in state.get('conversations',[]) if c['id']==body.conversation_id and c['user_id']==user['id']),None)
                msg=next((x for x in (conv or {}).get('messages',[]) if x['id']==body.message_id),None)
                if not msg: raise HTTPException(404,'전달할 대화를 찾지 못했습니다.')
                if any(q.get('message_id')==body.message_id for q in state.get('questions',[])):
                    return {'ok':True}
                context={'conversation_id':conv['id'],'message_id':msg['id'],'ai_answer':msg['answer'],'evidence':msg.get('evidence',[])}
            state.setdefault('questions',[]).append({'id':str(uuid.uuid4()),'question':body.content.strip(),'author':user['name'],'created_at':m.now(),'answer':None,**context})
            m.write_state(state)
        return {'ok':True}
    @router.post('/questions/{question_id}/answer')
    def reply(question_id:str,body:Question,user=Depends(m.current_user)):
        with m.LOCK:
            state=m.read_state();owner(state,user);approved(state);m.check_revision(state,body.revision)
            row=next((q for q in state.get('questions',[]) if q['id']==question_id),None)
            if not row: raise HTTPException(404,'질문을 찾지 못했습니다.')
            if not body.content.strip(): raise HTTPException(422,'답변을 입력해 주세요.')
            row.update(answer=body.content.strip(),answered_by=user['name'],answered_at=m.now());m.write_state(state)
        return {'ok':True}
    @router.post('/qa/stream')
    async def ask(body:Ask,user=Depends(m.current_user)):
        state=m.read_state();approved(state);m.check_revision(state,body.revision)
        if not body.question.strip():raise HTTPException(422,'질문을 입력해 주세요.')
        conversation=next((c for c in state.get('conversations',[]) if c['id']==body.conversation_id and c['user_id']==user['id']),None)
        if body.conversation_id and not conversation: raise HTTPException(404,'대화를 찾지 못했습니다.')
        conversation=conversation or {'id':str(uuid.uuid4()),'user_id':user['id'],'title':body.question[:40],'messages':[],'summary':''}
        def validate(answer,chunks):
            item=m.Item(title='답변',description=answer.answer,category='질문',priority='보통',evidence=[m.Evidence(**e.model_dump()) for e in answer.evidence])
            m.validate_evidence([item],state['documents'],True);m.validate_retrieved([item],chunks)
        async def run(report):
            result=await knowledge.answer_question(state,conversation,body.question,m.DB.parent,report,validate)
            if user['id']!=state['handover']['successor_id']: result['action']=None
            message={'id':str(uuid.uuid4()),'question':body.question,'created_at':m.now(),**result,'action_executed':False}
            conversation['messages'].append(message)
            if len(conversation['messages'])>8:
                report('summarize','업무 Q&A Agent가 이전 대화 맥락을 요약합니다.')
                summary=await json_call('업무 Q&A Agent','이전 대화 맥락을 1500자 이내로 요약한다. 업무 사실의 근거로 확정하지 마라. 출력 {"summary":"요약"}',{'summary':conversation.get('summary',''),'messages':conversation['messages'][-9:-8]})
                conversation['summary']=str(summary.get('summary',''))[:1500]
            with m.LOCK:
                current=m.read_state();approved(current);m.check_revision(current,body.revision)
                message['source_revision']=body.revision;message['action_revision']=body.revision+1
                histories=current.setdefault('conversations',[])
                histories[:]=[c for c in histories if c['id']!=conversation['id']];histories.append(conversation)
                m.write_state(current)
            report('done','답변을 저장했습니다. 근거 또는 작업 대상을 확인해 주세요.')
        return m.progress_response(run)
    @router.delete('/qa/{conversation_id}')
    def delete_conversation(conversation_id:str,revision:int,user=Depends(m.current_user)):
        with m.LOCK:
            state=m.read_state();m.check_revision(state,revision)
            if not any(c['id']==conversation_id and c['user_id']==user['id'] for c in state.get('conversations',[])):raise HTTPException(404,'대화를 찾지 못했습니다.')
            state['conversations']=[c for c in state['conversations'] if c['id']!=conversation_id];m.write_state(state)
        return {'ok':True}
    @router.post('/qa/action')
    async def confirm_action(body:ActionConfirm,user=Depends(m.current_user)):
        with m.LOCK:
            state=m.read_state();successor(state,user);m.check_revision(state,body.revision)
            conv=next((c for c in state.get('conversations',[]) if c['id']==body.conversation_id and c['user_id']==user['id']),None)
            msg=next((x for x in (conv or {}).get('messages',[]) if x['id']==body.message_id),None)
            if not msg or not msg.get('action') or msg.get('action_executed'):raise HTTPException(409,'실행 가능한 작업이 없거나 이미 처리했습니다.')
            if msg['action_revision']!=body.revision:raise HTTPException(409,'작업 제안 후 자료가 변경됐습니다. 다시 요청해 주세요.')
            action=msg['action'];valid_schedule(state)
            if action['kind']=='progress':
                persist_progress(state,ProgressEdit(revision=body.revision,item_ids=action['item_ids'],status=action['status']),user)
                msg['action_executed']=True;m.write_state(state);return {'ok':True}
        results=await calendar_api.sync_events(user,state,action['item_ids'])
        with m.LOCK:
            current=m.read_state()
            if current['revision']!=body.revision:
                raise HTTPException(409,'Google 등록 요청 중 인수인계 자료가 변경됐습니다. 일부 일정은 이미 등록되었을 수 있습니다. 최신 일정을 확인한 뒤 다시 등록하면 같은 일정이 갱신됩니다.')
            conv=next(c for c in current['conversations'] if c['id']==body.conversation_id)
            msg=next(x for x in conv['messages'] if x['id']==body.message_id)
            msg['action_executed']=all(r['status']=='success' for r in results);msg['action_revision']=body.revision+1
            current.setdefault('calendar_results',{})[user['id']]=results;m.write_state(current)
        return {'results':results}
    @router.post('/calendar/events')
    async def calendar_events(body:Events,user=Depends(m.current_user)):
        state=m.read_state();successor(state,user);valid_schedule(state);m.check_revision(state,body.revision)
        results=await calendar_api.sync_events(user,state,list(dict.fromkeys(body.item_ids)))
        with m.LOCK:
            current=m.read_state()
            if current['revision']!=body.revision:
                raise HTTPException(409,'Google 등록 요청 중 인수인계 자료가 변경됐습니다. 일부 일정은 이미 등록되었을 수 있습니다. 최신 일정을 확인한 뒤 다시 등록하면 같은 일정이 갱신됩니다.')
            current.setdefault('calendar_results',{})[user['id']]=results;m.write_state(current)
        return {'results':results}
    @router.post('/signature')
    def sign(body:Signature,user=Depends(m.current_user)):
        with m.LOCK:
            state=m.read_state();owner(state,user);valid_schedule(state);m.check_revision(state,body.revision)
            if not body.consent or body.name.strip()!=user['name']:raise HTTPException(422,'본인 성명을 입력하고 서명에 동의해 주세요.')
            state['signature']={'name':user['name'],'user_id':user['id'],'signed_at':datetime.now(ZoneInfo('Asia/Seoul')).isoformat(),'fingerprint':scheduling.fingerprint(state),'schedule_at':state['schedule']['confirmed_at']}
            m.write_state(state)
        return {'ok':True}
    @router.get('/export')
    def export(user=Depends(m.current_user)):
        state=m.read_state();owner(state,user);valid_schedule(state)
        signature=state.get('signature')
        if not signature or signature['fingerprint']!=scheduling.fingerprint(state) or signature['schedule_at']!=state['schedule']['confirmed_at']:
            raise HTTPException(409,'확정 내용과 일정을 확인하고 먼저 서명해 주세요.')
        content=build_docx(state,signature)
        return Response(content,media_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document',headers={'Content-Disposition':'attachment; filename="handover.docx"'})
    m.app.include_router(router,prefix='/api/handovers/{handover_id}',dependencies=[Depends(scope)])
    calendar_api.install(m)
