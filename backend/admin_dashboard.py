"""Read-only schedule summaries. Do not return checklist or document contents."""
from datetime import datetime, date
from zoneinfo import ZoneInfo
from backend import scheduling


def summarize(state, today=None):
    today = today or datetime.now(ZoneInfo('Asia/Seoul')).date()
    h = state['handover']
    ids = {item['id'] for item in state.get('items', [])}
    progress = state.get('progress', {})
    done = {key for key in ids if progress.get(key, {}).get('status') == 'done'}
    schedule = state.get('schedule', {})
    confirmed = schedule.get('confirmed', [])
    current = bool(confirmed) and state.get('status') == 'approved' and schedule.get('fingerprint') == scheduling.fingerprint(state)
    end = date.fromisoformat(h['end_date']) if h.get('end_date') else None
    remaining = (end - today).days if end else None
    overdue = {r['item_id'] for r in confirmed if r['item_id'] in ids and r['end'] < today.isoformat() and r['item_id'] not in done} if current else set()
    due = {r['item_id'] for r in confirmed if r['item_id'] in ids and r['end'] < today.isoformat()} if current else set()
    if confirmed and not current:
        status, reason = 'review', '내용 또는 기간이 변경되어 일정을 다시 확정해야 합니다.'
    elif current and ids and done == ids:
        status, reason = 'complete', '모든 업무의 인수가 완료되었습니다.'
    elif overdue or (end and remaining < 0):
        status, reason = 'delayed', f'기한이 지난 미완료 업무 {len(overdue)}개' if overdue else '인수인계 종료일이 지났으며 완료가 확인되지 않았습니다.'
    elif not current:
        status, reason = 'unscheduled', '확정된 일정이 없어 일정 준수 여부를 판단할 수 없습니다.'
    elif remaining is not None and 0 <= remaining <= 3:
        status, reason = 'soon', f'종료까지 {remaining}일 · 남은 업무 {len(ids - done)}개'
    else:
        status, reason = 'on_track', '확정 일정 기준 기한이 지난 미완료 업무가 없습니다.'
    return {
        'id':h['id'], 'name':h['name'], 'owner':h.get('owner', ''),
        'successors':h.get('successors') or [h.get('successor', '')],
        'start_date':h.get('start_date'), 'end_date':h.get('end_date'),
        'status':status, 'reason':reason, 'total':len(ids), 'done':len(done),
        'percent':round(len(done) / len(ids) * 100) if ids else 0,
        'overdue':len(overdue) if current else None,
        'due_count':len(due) if current else None,
        'due_done':len(due & done) if current else None,
        'days_remaining':remaining, 'schedule_current':current,
    }
