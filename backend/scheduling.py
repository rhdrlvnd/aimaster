"""Schedule proposals use AI ordering; calendar constraints are deterministic."""
from datetime import date, timedelta
import hashlib
import json
import re
from pydantic import BaseModel, Field, ConfigDict
from fastapi import HTTPException
from backend.agents import json_call, run_role
from backend import rag
from typing import Literal
from datetime import time

class ScheduleSettings(BaseModel):
    start: date
    end: date
    weekends: bool = False
    holidays: list[date] = Field(default_factory=list,max_length=100)
    durations: dict[str,int] = Field(default_factory=dict)
    dependencies: dict[str,list[str]] = Field(default_factory=dict)
    unit: Literal['day','hour','balanced'] = 'day'  # Preserve existing schedules.
    daily_hours: int = Field(default=4,ge=1,le=12)
    day_start: int = Field(default=9,ge=0,le=11)

class ScheduleRow(BaseModel):
    model_config=ConfigDict(extra='forbid')
    item_id: str
    start: date
    end: date
    start_time: time | None = None
    end_time: time | None = None
    reason: str = Field(default='',max_length=2000)

class OrderEntry(BaseModel):
    item_id: str
    reason: str = Field(max_length=2000)
class OrderResult(BaseModel):
    items: list[OrderEntry]

def fingerprint(state):
    return hashlib.sha256(json.dumps({'items':state['items'],'period':state['handover']},sort_keys=True,ensure_ascii=False).encode()).hexdigest()

def working(day, settings):
    return (settings.weekends or day.weekday()<5) and day not in settings.holidays

def validate_settings(state,settings):
    ids={i['id'] for i in state['items']}
    if settings.end < settings.start or (settings.end-settings.start).days>730:
        raise HTTPException(422,'일정 기간은 시작일 이후 2년 이내로 입력해 주세요.')
    h=state['handover']
    if not h.get('start_date') or not h.get('end_date'):
        raise HTTPException(422,'인수인계 시작일과 종료일을 먼저 입력해 주세요.')
    if settings.start < date.fromisoformat(h['start_date']) or settings.end > date.fromisoformat(h['end_date']):
        raise HTTPException(422,'일정은 인수인계 기간 안에 배치해 주세요.')
    if settings.unit!='balanced' and (set(settings.durations)!=ids or any(type(v)!=int or v<1 or v>365 for v in settings.durations.values())):
        raise HTTPException(422,'모든 업무의 소요량을 1~365 범위의 정수로 입력해 주세요. 시간 단위 일정은 시간 수를 입력합니다.')
    if set(settings.dependencies)-ids: raise HTTPException(422,'알 수 없는 업무입니다.')
    for key, deps in settings.dependencies.items():
        if key in deps or set(deps)-ids or len(deps)!=len(set(deps)):
            raise HTTPException(422,'선행 업무를 확인해 주세요.')
    resolved=set()
    while len(resolved)<len(ids):
        ready={key for key in ids-resolved if set(settings.dependencies.get(key,[]))<=resolved}
        if not ready:
            # Follow unresolved prerequisites until the actual cycle repeats.
            path=[]; key=next(i['id'] for i in state['items'] if i['id'] not in resolved)
            while key not in path:
                path.append(key)
                key=next(d for d in settings.dependencies[key] if d not in resolved)
            cycle=path[path.index(key):]+[key]
            titles={i['id']:i['title'] for i in state['items']}
            raise HTTPException(422,'선행 업무가 서로 순환합니다: '+' → '.join(titles[k] for k in cycle)+'. 표시된 선행 관계 중 잘못 연결된 관계를 수정해 주세요.')
        resolved |= ready

def validate_capacity(settings, fixed, start):
    """Reject impossible serial allocation before spending time on an AI call."""
    required=sum(days for key,days in settings.durations.items() if key not in fixed)
    available=0
    day=start
    while day<=settings.end:
        if working(day,settings) and not any(date.fromisoformat(r['start'])<=day<=date.fromisoformat(r['end']) for r in fixed.values()):
            available+=1
        day+=timedelta(days=1)
    if required>available:
        raise HTTPException(422,f'현재는 하루에 한 업무씩 배치합니다. 남은 업무에 총 {required}업무일이 필요하지만, 선택한 기간의 배치 가능한 날은 {available}업무일입니다. {required-available}업무일이 부족하므로 기간이나 소요 업무일을 조정해 주세요. 기존 일정은 유지됩니다.')

def validate_rows(state, settings, rows, preserved=None):
    validate_settings(state,settings)
    if settings.unit=='balanced':
        by_id={r.item_id:r for r in rows}
        if set(by_id)!={i['id'] for i in state['items']} or len(rows)!=len(by_id):
            raise HTTPException(422,'모든 업무를 일정에 한 번씩 포함해 주세요.')
        for row in rows:
            if preserved and row.item_id in preserved:
                old=ScheduleRow(**preserved[row.item_id])
                if row!=old: raise HTTPException(422,'완료된 업무 일정은 변경할 수 없습니다.')
                continue
            if row.start!=row.end or not settings.start<=row.start<=settings.end or not working(row.start,settings) or row.start_time is not None or row.end_time is not None:
                raise HTTPException(422,'업무는 기간 안의 업무일에 날짜 단위로 배치해 주세요.')
            if any(by_id[d].end>row.start for d in settings.dependencies.get(row.item_id,[])):
                raise HTTPException(422,'선행 업무보다 앞선 날짜로 이동할 수 없습니다.')
        return
    if settings.unit=='hour':
        return validate_hour_rows(state,settings,rows,preserved)
    by_id={r.item_id:r for r in rows}
    ids={i['id'] for i in state['items']}
    if set(by_id)!=ids or len(rows)!=len(ids): raise HTTPException(422,'모든 업무를 일정에 한 번씩 포함해 주세요.')
    for row in rows:
        if row.start<settings.start or row.end>settings.end or row.end<row.start:
            raise HTTPException(422,'일정이 기간을 벗어났거나 종료일이 시작일보다 빠릅니다.')
        days=[row.start+timedelta(days=n) for n in range((row.end-row.start).days+1)]
        if not working(row.start,settings) or not working(row.end,settings) or sum(working(d,settings) for d in days)!=settings.durations[row.item_id]:
            raise HTTPException(422,'업무별 소요 업무일·주말·휴일 조건을 확인해 주세요.')
        if any(by_id[d].end>=row.start for d in settings.dependencies.get(row.item_id,[])):
            raise HTTPException(422,'선행 업무가 끝난 다음에 후속 업무를 배치해 주세요.')
        if preserved and row.item_id in preserved:
            old=preserved[row.item_id]
            if str(row.start)!=old['start'] or str(row.end)!=old['end']:
                raise HTTPException(422,'완료된 업무 일정은 변경할 수 없습니다.')

async def propose(state, settings, reschedule, report):
    validate_settings(state,settings)
    old=state.get('schedule',{}).get('confirmed',[]) or list(state.get('schedule',{}).get('preserved_completed',{}).values())
    progress=state.get('progress',{})
    fixed={r['item_id']:r for r in old if progress.get(r['item_id'],{}).get('status')=='done'}
    if reschedule and not old: raise HTTPException(422,'확정 일정이 있어야 재조정할 수 있습니다.')
    if fixed and not reschedule: raise HTTPException(409,'완료된 업무가 있습니다. 일정 재조정을 사용해 주세요.')
    from zoneinfo import ZoneInfo
    from datetime import datetime
    cursor=max(settings.start, datetime.now(ZoneInfo('Asia/Seoul')).date()) if reschedule or settings.unit=='balanced' else settings.start
    slots=hour_slots(settings,cursor) if settings.unit=='hour' else []
    if settings.unit=='hour':
        occupied=fixed_slots(settings,fixed)
        required=sum(v for k,v in settings.durations.items() if k not in fixed)
        available=sum(slot not in occupied for slot in slots)
        if required>available:
            raise HTTPException(422,f'총 {required}시간이 필요하지만 배치 가능한 시간은 {available}시간입니다. 기간이나 하루 가능 시간을 조정해 주세요.')
    elif settings.unit!='balanced':
        validate_capacity(settings, fixed if reschedule else {}, cursor)
    elif cursor>settings.end or not any(working(cursor+timedelta(days=n),settings) for n in range((settings.end-cursor).days+1)):
        if len(fixed)!=len(state['items']): raise HTTPException(422,'남은 인수인계 기간에 배치 가능한 업무일이 없습니다. 기간을 조정해 주세요.')
    report('analyze',f'{rag.chat_model()} · 일정 계획 Agent가 중요도와 선행 조건을 고려하고 있습니다.')
    async def plan(payload):
        return await json_call('일정 계획 Agent','인수인계 일정의 업무 배치 순서를 제안한다. 제공된 모든 item id를 정확히 한 번 포함한다. 중요도와 명시된 선행 조건을 고려하고 이유를 쓴다. 날짜나 소요 기간을 지어내지 마라. 출력: {"items":[{"item_id":"id","reason":"배치 이유"}]}', payload)
    planning_items=[{k:i[k] for k in ('id','title','description','priority') if k in i} for i in state['items']]
    result=OrderResult.model_validate(await run_role('schedule_planner',plan,{'items':planning_items,'settings':settings.model_dump(mode='json'),'completed':list(fixed),'reschedule':reschedule}))
    ids={i['id'] for i in state['items']}
    if {r.item_id for r in result.items}!=ids or len(result.items)!=len(ids):
        raise HTTPException(502,'AI 일정 순서에 업무 누락이나 중복이 있습니다. 다시 생성해 주세요.')
    for entry in result.items:
        if re.search(r'[\u3400-\u9fff\u3040-\u30ff]',entry.reason):
            entry.reason='선행 업무와 입력한 소요량을 기준으로 가능한 시간에 배치했습니다.'
    report('validate','업무 배분·휴일·선행 조건·완료 업무 유지 여부를 검사합니다.')
    if settings.unit=='balanced':
        return allocate_balanced(state,settings,result.items,fixed if reschedule else {},cursor)
    if settings.unit=='hour':
        return allocate_hours(state,settings,result.items,fixed if reschedule else {},slots)
    rows={key:ScheduleRow(**row) for key,row in fixed.items()} if reschedule else {}
    pending=[r for r in result.items if r.item_id not in rows]
    while pending:
        entry=next((r for r in pending if set(settings.dependencies.get(r.item_id,[]))<=set(rows)),None)
        if entry is None: raise HTTPException(422,'완료된 업무와 선행 조건을 확인해 주세요.')
        start=max([cursor]+[rows[d].end+timedelta(days=1) for d in settings.dependencies.get(entry.item_id,[])])
        # One owner/successor pair: allocate serially, avoiding completed dates.
        occupied=[r for r in rows.values()]
        days=[]; day=start
        while len(days)<settings.durations[entry.item_id] and day<=settings.end:
            if working(day,settings) and not any(r.start<=day<=r.end for r in occupied): days.append(day)
            elif any(r.start<=day<=r.end for r in occupied): days=[]
            day+=timedelta(days=1)
        if len(days)<settings.durations[entry.item_id]:
            raise HTTPException(422,'기간 안에 모든 업무를 배치할 수 없습니다. 기간이나 업무별 소요 일수를 검토해 주세요. 기존 일정은 유지됩니다.')
        rows[entry.item_id]=ScheduleRow(item_id=entry.item_id,start=days[0],end=days[-1],reason=entry.reason)
        cursor=days[-1]+timedelta(days=1); pending.remove(entry)
    output=list(rows.values())
    validate_rows(state,settings,output,fixed if reschedule else None)
    return [r.model_dump(mode='json') for r in output]

def allocate_balanced(state,settings,entries,fixed,start):
    days=[start+timedelta(days=n) for n in range(max(0,(settings.end-start).days+1)) if working(start+timedelta(days=n),settings)]
    rows={key:ScheduleRow(**row) for key,row in fixed.items()}
    pending=[entry for entry in entries if entry.item_id not in rows]
    total=len(pending)
    if total and not days: raise HTTPException(422,'배치 가능한 업무일이 없습니다.')
    for index in range(total):
        entry=next((e for e in pending if set(settings.dependencies.get(e.item_id,[]))<=rows.keys()),None)
        if entry is None: raise HTTPException(422,'선행 업무 관계를 확인해 주세요.')
        slot=(index*len(days)//total) if total>=len(days) else (round(index*(len(days)-1)/(total-1)) if total>1 else 0)
        earliest=max([days[slot]]+[rows[d].end for d in settings.dependencies.get(entry.item_id,[])])
        day=next((d for d in days if d>=earliest),None)
        if day is None: raise HTTPException(422,'선행 업무 이후 배치 가능한 날짜가 없습니다.')
        rows[entry.item_id]=ScheduleRow(item_id=entry.item_id,start=day,end=day,reason=entry.reason)
        pending.remove(entry)
    output=list(rows.values())
    validate_rows(state,settings,output,fixed)
    return [r.model_dump(mode='json') for r in output]

def hour_slots(settings,start=None):
    slots=[]; day=start or settings.start
    while day<=settings.end:
        if working(day,settings):
            slots.extend((day,h) for h in range(settings.day_start,settings.day_start+settings.daily_hours))
        day+=timedelta(days=1)
    return slots

def row_slots(row,settings):
    if row.start_time is None or row.end_time is None:
        raise HTTPException(422,'시간 단위 일정의 시작·종료 시간을 입력해 주세요.')
    if row.start_time.minute or row.end_time.minute or row.start_time.second or row.end_time.second:
        raise HTTPException(422,'일정은 1시간 단위로 입력해 주세요.')
    start=(row.start,row.start_time.hour); end=(row.end,row.end_time.hour)
    slots=[s for s in hour_slots(settings) if start<=s<end]
    if not slots or slots[0]!=start or (slots[-1][0],slots[-1][1]+1)!=end:
        raise HTTPException(422,'일정은 기간과 하루 인수인계 가능 시간 안에 배치해 주세요.')
    return slots

def fixed_slots(settings,fixed):
    occupied=set()
    for raw in fixed.values():
        if not raw.get('start_time') or not raw.get('end_time'):
            raise HTTPException(422,'완료된 일 단위 일정이 있어 시간 단위로 변경할 수 없습니다. 기존 단위로 재조정해 주세요.')
        occupied.update(row_slots(ScheduleRow(**raw),settings))
    return occupied

def validate_hour_rows(state,settings,rows,preserved=None):
    by_id={r.item_id:r for r in rows}
    if set(by_id)!={i['id'] for i in state['items']} or len(by_id)!=len(rows):
        raise HTTPException(422,'모든 업무를 일정에 한 번씩 포함해 주세요.')
    occupied=set()
    for row in rows:
        slots=row_slots(row,settings)
        if len(slots)!=settings.durations[row.item_id] or occupied.intersection(slots):
            raise HTTPException(422,'소요 시간이 맞지 않거나 다른 업무와 시간이 겹칩니다.')
        occupied.update(slots)
        for dep in settings.dependencies.get(row.item_id,[]):
            previous=by_id[dep]
            if previous.end_time is None or (previous.end,previous.end_time)>(row.start,row.start_time):
                raise HTTPException(422,'선행 업무 종료 후에 후속 업무를 배치해 주세요.')
        if preserved and row.item_id in preserved:
            old=ScheduleRow(**preserved[row.item_id])
            if (row.start,row.end,row.start_time,row.end_time)!=(old.start,old.end,old.start_time,old.end_time):
                raise HTTPException(422,'완료된 업무 일정은 변경할 수 없습니다.')

def allocate_hours(state,settings,entries,fixed,slots):
    rows={k:ScheduleRow(**r) for k,r in fixed.items()}
    occupied=fixed_slots(settings,fixed)
    pending=[r for r in entries if r.item_id not in rows]
    while pending:
        entry=next((r for r in pending if set(settings.dependencies.get(r.item_id,[]))<=set(rows)),None)
        if entry is None: raise HTTPException(422,'완료된 업무와 선행 조건을 확인해 주세요.')
        earliest=max([(rows[d].end,rows[d].end_time.hour) for d in settings.dependencies.get(entry.item_id,[])],default=(settings.start,0))
        selected=[]
        for slot in slots:
            if slot<earliest: continue
            if slot in occupied: selected=[]; continue
            selected.append(slot)
            if len(selected)==settings.durations[entry.item_id]: break
        if len(selected)!=settings.durations[entry.item_id]:
            raise HTTPException(422,'선행 조건과 완료 일정을 유지하면서 기간 안에 배치할 수 없습니다. 기간이나 소요 시간을 조정해 주세요.')
        first,last=selected[0],selected[-1]
        rows[entry.item_id]=ScheduleRow(item_id=entry.item_id,start=first[0],end=last[0],start_time=time(first[1]),end_time=time(last[1]+1),reason=entry.reason)
        occupied.update(selected);pending.remove(entry)
    validate_rows(state,settings,list(rows.values()),fixed)
    return [r.model_dump(mode='json') for r in rows.values()]
