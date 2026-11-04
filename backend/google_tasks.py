"""Tasks registration and daily, three-way completion reconciliation."""
import asyncio
import hashlib
import logging
from contextlib import asynccontextmanager, suppress
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from urllib.parse import quote
import httpx
from fastapi import HTTPException
from backend import google_store as store, calendar_api, scheduling
from backend.participants import is_successor

TASKS_SCOPE = 'https://www.googleapis.com/auth/tasks'
ROOT = 'https://tasks.googleapis.com/tasks/v1/lists/@default/tasks'
KST = ZoneInfo('Asia/Seoul')
log = logging.getLogger('uvicorn.error.handover.tasks')


def now():
    return datetime.now(KST).isoformat()


def local_status(state, key):
    return state.get('progress', {}).get(key, {}).get('status', 'todo')


def remote_status(status):
    return 'completed' if status == 'done' else 'needsAction'


def check_state(state, user_id):
    if not is_successor(state, user_id):
        raise HTTPException(403, '인수자만 Google Tasks를 연결할 수 있습니다.')
    schedule = state.get('schedule', {})
    if state['status'] != 'approved' or not schedule.get('confirmed') or schedule.get('fingerprint') != scheduling.fingerprint(state):
        raise HTTPException(409, '최신 체크리스트와 일정을 확정한 뒤 Tasks를 동기화해 주세요.')


@asynccontextmanager
async def lease(name):
    owner = store.acquire(name)
    if not owner:
        raise HTTPException(409, '같은 Google 작업을 처리 중입니다. 잠시 후 다시 시도해 주세요.')
    async def heartbeat():
        while True:
            await asyncio.sleep(30)
            store.renew(name, owner)
    task = asyncio.create_task(heartbeat())
    try:
        yield
    finally:
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task
        store.release(name, owner)


def failure(response):
    if response.status_code == 403:
        return 'Google Tasks API 사용 설정과 Tasks 접근 동의를 확인해 주세요.'
    if response.status_code == 401:
        return 'Google 연결이 만료됐습니다. 다시 연결해 주세요.'
    if response.status_code == 412:
        return 'Google에서 동시에 변경되었습니다. 다음 배치에서 다시 확인합니다.'
    return f'Google Tasks 응답 오류 ({response.status_code}). 다음 배치에서 다시 확인합니다.'


async def response_json(response):
    if response.status_code not in (200, 201):
        raise HTTPException(502, failure(response))
    try:
        value = response.json()
        if not isinstance(value, dict):
            raise ValueError()
        return value
    except ValueError:
        raise HTTPException(502, 'Google Tasks 응답을 읽지 못했습니다.')


async def list_tasks(http):
    values = []
    params = {'maxResults': 100, 'showCompleted': 'true', 'showHidden': 'true', 'showDeleted': 'true'}
    seen = set()
    while True:
        body = await response_json(await http.get(ROOT, params=params))
        values.extend(body.get('items', []))
        cursor = body.get('nextPageToken')
        if not cursor:
            return values
        if cursor in seen:
            raise HTTPException(502, 'Google Tasks 페이지 정보를 확인하지 못했습니다.')
        seen.add(cursor)
        params['pageToken'] = cursor


def credentials(user):
    value = calendar_api.saved_token(user['id'])
    if not value or TASKS_SCOPE not in value.get('scope', '').split() or not value.get('account_id'):
        raise HTTPException(409, 'Google Tasks 권한으로 다시 연결해 주세요.')
    return value


def marker(user_id, account_id, handover_id, item_id):
    digest = hashlib.sha256('|'.join((user_id, account_id, handover_id, item_id)).encode()).hexdigest()
    return 'handover-ref:' + digest


def public_status(user, state):
    try: value = calendar_api.saved_token(user['id'])
    except HTTPException: value = None
    links = store.links(user['id'], value['account_id'], state['handover']['id']) if value and value.get('account_id') else {}
    active = {i['id'] for i in state['items']}
    return {
        'schedule': '매일 오전 6시 (한국 시간)',
        'next_run': next_run().isoformat(),
        'linked_count': sum(bool(v.get('task_id')) for k, v in links.items() if k in active),
        'items': [{'item_id': k, 'status': v.get('status', 'registered'), 'detail': v.get('detail', ''),
                   'pending': local_status(state,k) != v.get('local_status'),
                   'checked_at': v.get('checked_at'), 'synced_at': v.get('synced_at')}
                  for k, v in links.items() if k in active],
        'legacy_events': any(r.get('event_id') for r in state.get('calendar_results', {}).get(user['id'], [])),
    }


def next_run(clock=None):
    clock = (clock or datetime.now(KST)).astimezone(KST)
    due = clock.replace(hour=6, minute=0, second=0, microsecond=0)
    return due if clock < due else due + timedelta(days=1)


async def register(m, user, ids, revision, replace_events=False):
    value = credentials(user)
    uid, account_id = user['id'], value['account_id']
    state = m.read_state()
    check_state(state, uid)
    m.check_revision(state, revision)
    hid = state['handover']['id']
    rows = {r['item_id']: r for r in state['schedule']['confirmed']}
    items = {i['id']: i for i in state['items']}
    if set(ids)-set(rows) or len(set(ids)) != len(ids):
        raise HTTPException(422, '등록할 확정 업무를 확인해 주세요.')
    async with lease(f'tasks:{uid}:{hid}'):
        token = await calendar_api.access_token(user)
        links = store.links(uid, account_id, hid)
        results = []
        async with httpx.AsyncClient(timeout=30, headers={'Authorization': 'Bearer '+token}) as http:
            # Recovery of a lost insert response must use the exact private marker,
            # never a title match. Complete/hidden tasks are included.
            existing = await list_tasks(http)
            for key in ids:
                current = m.read_state()
                check_state(current, uid)
                m.check_revision(current, revision)
                if credentials(user)['account_id'] != account_id:
                    raise HTTPException(409, 'Google 연결 계정이 변경되었습니다.')
                ref = marker(uid, account_id, hid, key)
                link = links.get(key, {})
                payload = {'title': items[key]['title'], 'notes': state['handover']['name']+'\n'+items[key]['description']+'\n'+ref,
                           'due': rows[key]['start']+'T00:00:00.000Z'}
                try:
                    if not link.get('task_id'):
                        found = [t for t in existing if ref in t.get('notes', '').splitlines() and not t.get('deleted')]
                        if len(found) > 1:
                            raise HTTPException(409, '같은 업무의 Tasks가 여러 개입니다. Google에서 중복을 정리해 주세요.')
                        if found:
                            task = found[0]
                        elif link.get('uncertain'):
                            raise HTTPException(409, '이전 등록 결과를 확인하지 못했습니다. 중복 방지를 위해 재생성을 보류했습니다. Google Tasks 목록을 확인해 주세요.')
                        else:
                            link = {'uncertain': True, 'local_status': local_status(state, key)}
                            store.save_link(uid, account_id, hid, key, link)
                            response = await http.post(ROOT, json={**payload, 'status': remote_status(local_status(state, key))})
                            if 400 <= response.status_code < 500:
                                link['uncertain'] = False
                            task = await response_json(response)
                        if not task.get('id') or task.get('status') not in ('needsAction', 'completed'):
                            raise HTTPException(502, '생성한 Task 정보를 확인하지 못했습니다.')
                        link.update(task_id=task['id'], uncertain=False, local_status=link.get('local_status', local_status(state, key)),
                                    remote_status=remote_status(link.get('local_status', local_status(state, key))), status='registered', detail='', synced_at=now())
                        # Save the mapping immediately, even if the workspace changes.
                        store.save_link(uid, account_id, hid, key, link)
                    else:
                        # Re-registration updates title/date only. Completion is daily.
                        task = next((t for t in existing if t.get('id') == link['task_id']), None)
                        if not task or task.get('deleted'):
                            raise HTTPException(409, 'Google에서 삭제된 Task입니다. 자동으로 재생성하거나 업무를 완료하지 않습니다.')
                        headers = {'If-Match': task['etag']} if task.get('etag') else {}
                        await response_json(await http.patch(ROOT+'/'+quote(link['task_id'], safe=''), json=payload, headers=headers))
                    link.update(status='registered', detail='완료 상태는 매일 오전 6시에 동기화합니다.')
                    if replace_events:
                        await remove_old_event(http, uid, hid, key)
                    result = {'item_id': key, 'status': 'success', 'task_id': link['task_id']}
                except (HTTPException, httpx.HTTPError) as exc:
                    detail = exc.detail if isinstance(exc, HTTPException) else 'Google 응답을 받지 못했습니다. 등록 결과를 확인한 뒤 다시 시도해 주세요.'
                    link.update(status='error', detail=detail)
                    result = {'item_id': key, 'status': 'failed', 'detail': detail}
                store.save_link(uid, account_id, hid, key, link)
                results.append(result)
        return results


async def remove_old_event(http, uid, hid, key):
    event_id = 'h'+hashlib.sha256((uid+hid+key).encode()).hexdigest()[:40]
    url = 'https://www.googleapis.com/calendar/v3/calendars/primary/events/'+event_id
    response = await http.get(url)
    if response.status_code in (404, 410):
        return
    body = await response_json(response)
    private = body.get('extendedProperties', {}).get('private', {})
    if private.get('handover_id') != hid or private.get('item_id') != key:
        raise HTTPException(409, '기존 이벤트의 소속을 확인하지 못해 삭제하지 않았습니다.')
    response = await http.delete(url)
    if response.status_code not in (200, 204, 404, 410):
        raise HTTPException(502, 'Task는 등록됐지만 기존 이벤트를 정리하지 못했습니다. 다시 등록해 주세요.')


def plan(state, links, remote):
    """No I/O: three-way status comparison and final dependency validation."""
    pull, push, aligned, problems = {}, {}, [], {}
    active = {i['id'] for i in state['items']}
    for key, link in links.items():
        if key not in active or not link.get('task_id'):
            continue
        task = remote.get(link['task_id'])
        if not task or task.get('deleted'):
            problems[key] = 'Google Task가 삭제되었거나 조회되지 않습니다. 업무 상태는 유지했습니다.'
            continue
        rs = task.get('status')
        if rs not in ('needsAction', 'completed'):
            problems[key] = 'Google Task 상태를 확인하지 못했습니다.'
            continue
        ls = local_status(state, key)
        if remote_status(ls) == rs:
            aligned.append(key)
        elif ls != link.get('local_status') and rs != link.get('remote_status'):
            problems[key] = '양쪽 상태가 함께 변경되었습니다. 원하는 상태로 양쪽을 맞춘 뒤 다음 배치를 기다려 주세요.'
        elif ls != link.get('local_status'):
            push[key] = rs
        elif rs != link.get('remote_status'):
            pull[key] = 'done' if rs == 'completed' else 'todo'
        else:
            problems[key] = '동기화 기준 상태가 달라 확인이 필요합니다.'
    # Validate the collective final state: a chain completed/undone together is valid.
    deps = state['schedule']['settings'].get('dependencies', {})
    while True:
        proposed = {key: pull.get(key, local_status(state, key)) for key in active}
        invalid = {key for key in active if proposed[key] == 'done' and any(proposed.get(p) != 'done' for p in deps.get(key, []))}
        remove = {key for key in invalid if key in pull}
        for key in invalid:
            remove.update(p for p in deps.get(key, []) if p in pull and proposed.get(p) != 'done')
        if not remove:
            break
        for key in remove:
            pull.pop(key)
            problems[key] = '선행·후속 업무 완료 조건과 충돌하여 반영하지 않았습니다. 양쪽 업무 상태를 확인해 주세요.'
    return pull, push, aligned, problems


async def synchronize(m, user, account_id, hid, persist_progress):
    uid = user['id']
    token_context = m.HANDOVER_ID.set(hid)
    try:
        async with lease(f'tasks:{uid}:{hid}'):
            state = m.read_state()
            check_state(state, uid)
            if credentials(user)['account_id'] != account_id:
                return
            token = await calendar_api.access_token(user)
            links = store.links(uid, account_id, hid)
            results = []
            async with httpx.AsyncClient(timeout=30, headers={'Authorization': 'Bearer '+token}) as http:
                remote = {t['id']: t for t in await list_tasks(http) if t.get('id')}
                pull, push, aligned, problems = plan(state, links, remote)
                with m.LOCK:
                    current = m.read_state()
                    check_state(current, uid)
                    m.check_revision(current, state['revision'])
                    for status in ('todo', 'done'):
                        ids = [key for key, value in pull.items() if value == status]
                        if ids:
                            from backend.features import ProgressEdit
                            persist_progress(current, ProgressEdit(revision=current['revision'], item_ids=ids, status=status), user)
                    if pull:
                        m.write_state(current)
                for key in aligned + list(pull):
                    links[key].update(local_status=local_status(current, key), remote_status=remote[links[key]['task_id']]['status'],
                                      status='synced', detail='', checked_at=now(), synced_at=now())
                    store.save_link(uid, account_id, hid, key, links[key])
                for key in push:
                    try:
                        latest = m.read_state()
                        check_state(latest, uid)
                        # Never transmit a stale local completion after a concurrent edit.
                        if latest.get('progress', {}).get(key) != state.get('progress', {}).get(key) or latest['schedule'] != state['schedule']:
                            raise HTTPException(409, '처리 중 업무가 변경되어 다음 배치에서 다시 확인합니다.')
                        if credentials(user)['account_id'] != account_id:
                            raise HTTPException(409, 'Google 연결 계정이 변경되었습니다.')
                        task = remote[links[key]['task_id']]
                        payload = {'status': remote_status(local_status(state, key))}
                        if payload['status'] == 'needsAction':
                            payload['completed'] = None
                        headers = {'If-Match': task['etag']} if task.get('etag') else {}
                        updated = await response_json(await http.patch(ROOT+'/'+quote(task['id'], safe=''), json=payload, headers=headers))
                        if updated.get('status') != payload['status']:
                            raise HTTPException(502, 'Google에 반영된 완료 상태를 확인하지 못했습니다.')
                        links[key].update(local_status=local_status(state, key), remote_status=payload['status'], status='synced', detail='', checked_at=now(), synced_at=now())
                        store.save_link(uid, account_id, hid, key, links[key])
                    except (HTTPException, httpx.HTTPError) as exc:
                        problems[key] = exc.detail if isinstance(exc, HTTPException) else 'Google 연결 오류로 반영하지 못했습니다. 다음 배치에서 재시도합니다.'
                for key, detail in problems.items():
                    links[key].update(status='attention', detail=detail, checked_at=now())
                    store.save_link(uid, account_id, hid, key, links[key])
                results = [{'item_id': key, 'status': 'failed', 'detail': value} for key, value in problems.items()]
            return results
    finally:
        m.HANDOVER_ID.reset(token_context)


async def run_due(m, persist_progress, clock=None):
    clock = (clock or datetime.now(KST)).astimezone(KST)
    if clock.hour < 6:
        return False
    day = clock.date().isoformat()
    previous = store.batch_run(day)
    if previous and previous.get('finished_at'):
        return False
    try:
        async with lease('google-daily-batch'):
            previous = store.batch_run(day)
            if previous and previous.get('finished_at'):
                return False
            result = {'started_at': now(), 'targets': 0, 'failed_targets': 0}
            store.batch_run(day, result)
            for uid, account_id, hid in store.targets():
                try:
                    user = next((u for u in m.DEMO_USERS if u['id'] == uid), None)
                    saved = calendar_api.saved_token(uid)
                    if not user or not saved or saved.get('account_id') != account_id:
                        continue
                    result['targets'] += 1
                    errors = await synchronize(m, user, account_id, hid, persist_progress)
                    if errors:
                        result['failed_targets'] += 1
                except Exception as exc:
                    result['failed_targets'] += 1
                    detail = exc.detail if isinstance(exc, HTTPException) else 'Google 동기화 중 오류가 발생했습니다. 다음 배치에서 재시도합니다.'
                    for key, link in store.links(uid, account_id, hid).items():
                        link.update(status='error', detail=detail, checked_at=now())
                        store.save_link(uid, account_id, hid, key, link)
                    log.warning('Google Tasks batch failed type=%s', type(exc).__name__)
            result['finished_at'] = now()
            store.batch_run(day, result)
            return True
    except HTTPException as exc:
        if exc.status_code == 409:
            return False
        raise


def install_batch(m, persist_progress):
    async def worker():
        while True:
            try:
                await run_due(m, persist_progress)
            except Exception as exc:
                log.warning('Google Tasks scheduler error type=%s', type(exc).__name__)
            await asyncio.sleep(30)
    async def start():
        m.app.state.google_tasks_worker = asyncio.create_task(worker())
    async def stop():
        task = getattr(m.app.state, 'google_tasks_worker', None)
        if task:
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task
    m.app.add_event_handler('startup', start)
    m.app.add_event_handler('shutdown', stop)
