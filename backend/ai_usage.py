"""API-reported AI usage only. Never persist prompts, documents or credentials."""
import asyncio
import json
import logging
import re
import sqlite3
import time
import uuid
from contextlib import closing
from contextvars import ContextVar
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Literal
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException
from starlette.requests import Request


log = logging.getLogger('uvicorn.error.handover.usage')
KST = ZoneInfo('Asia/Seoul')
OPERATIONS = {
    'document_analysis': '문서 분석', 'checklist': '체크리스트 생성',
    'dependencies': '선행 업무 제안', 'schedule': '일정 계획',
    'qa': '업무 질문', 'other': '기타 AI 작업',
}


@dataclass(frozen=True)
class UsageContext:
    db: Path
    handover_id: str | None = None
    user_id: str | None = None
    operation: str = 'other'


CONTEXT = ContextVar('ai_usage_context', default=None)


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def operation_for_path(path):
    if re.search(r'/documents(?:/|$)', path):
        return 'document_analysis'
    if path.endswith('/checklist/dependencies/stream'):
        return 'dependencies'
    if re.search(r'/generate(?:/stream)?$', path) and '/schedule/' not in path:
        return 'checklist'
    if path.endswith('/schedule/generate/stream'):
        return 'schedule'
    if path.endswith('/qa/stream'):
        return 'qa'
    return 'other'


class UsageContextMiddleware:
    """Pure ASGI middleware keeps attribution until a streamed body finishes."""
    def __init__(self, app, module):
        self.app = app
        self.module = module

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http':
            return await self.app(scope, receive, send)
        request = Request(scope)
        match = re.match(r'^/api/handovers/([0-9a-fA-F-]{36})(?:/|$)', request.url.path)
        user_id = self.module.SESSIONS.get(request.cookies.get('handover_session'))
        token = CONTEXT.set(UsageContext(
            Path(self.module.DB), match.group(1) if match else None,
            user_id, operation_for_path(request.url.path)))
        try:
            await self.app(scope, receive, send)
        finally:
            CONTEXT.reset(token)


def ensure_storage(path):
    with closing(sqlite3.connect(path, timeout=15)) as db:
        db.execute('''CREATE TABLE IF NOT EXISTS ai_usage_events (
            id TEXT PRIMARY KEY, created_at TEXT NOT NULL,
            handover_id TEXT, user_id TEXT, operation TEXT NOT NULL,
            model TEXT NOT NULL, route TEXT NOT NULL, attempt INTEGER NOT NULL,
            status TEXT NOT NULL, http_status INTEGER, elapsed_ms INTEGER NOT NULL,
            usage_known INTEGER NOT NULL, input_tokens INTEGER, output_tokens INTEGER,
            total_tokens INTEGER, cached_input_tokens INTEGER, reasoning_tokens INTEGER
        )''')
        db.execute('CREATE INDEX IF NOT EXISTS ai_usage_created ON ai_usage_events(created_at)')
        db.execute('CREATE TABLE IF NOT EXISTS ai_usage_settings (name TEXT PRIMARY KEY, payload TEXT NOT NULL)')
        db.execute('INSERT OR IGNORE INTO ai_usage_settings VALUES (?, ?)',
                   ('recording_started_at', json.dumps(utc_now())))
        db.commit()


def _integer(value):
    return value if type(value) is int and 0 <= value <= 10**12 else None


def normalize_usage(data, route):
    result = dict(usage_known=0, input_tokens=None, output_tokens=None,
                  total_tokens=None, cached_input_tokens=None, reasoning_tokens=None)
    usage = data.get('usage') if isinstance(data, dict) else None
    if not isinstance(usage, dict):
        return result
    incoming = _integer(usage.get('prompt_tokens', usage.get('input_tokens')))
    outgoing = 0 if route == 'embeddings' else _integer(usage.get('completion_tokens', usage.get('output_tokens')))
    details_in = usage.get('prompt_tokens_details', usage.get('input_tokens_details')) or {}
    details_out = usage.get('completion_tokens_details', usage.get('output_tokens_details')) or {}
    if not isinstance(details_in, dict) or not isinstance(details_out, dict):
        return result
    cached = _integer(details_in.get('cached_tokens', 0))
    reasoning = _integer(details_out.get('reasoning_tokens', 0))
    if incoming is None or outgoing is None or cached is None or reasoning is None:
        return result
    if cached > incoming or reasoning > outgoing:
        return result
    # Cache and reasoning tokens are subsets, never extra tokens to add again.
    total = _integer(usage.get('total_tokens'))
    if 'total_tokens' in usage and (total is None or total != incoming + outgoing):
        return result
    result.update(usage_known=1, input_tokens=incoming, output_tokens=outgoing,
                  total_tokens=total if total is not None else incoming + outgoing,
                  cached_input_tokens=cached, reasoning_tokens=reasoning)
    return result


def record(context, *, model, route, attempt, started_at, elapsed_ms, response=None, error=None):
    if context is None:
        return  # Direct library/test calls do not write to the application database.
    data = None
    status_code = None
    if response is not None:
        raw_status = getattr(response, 'status_code', None)
        status_code = raw_status if type(raw_status) is int else None
        try:
            data = response.json()
        except (ValueError, TypeError):
            pass
    tokens = normalize_usage(data, route)
    status = 'cancelled' if isinstance(error, asyncio.CancelledError) else (
        'transport_error' if error is not None else ('success' if status_code and 200 <= status_code < 300 else 'http_error'))
    # Only this fixed allowlist is persisted, never the request/response body.
    row = dict(id=str(uuid.uuid4()), created_at=started_at,
               handover_id=context.handover_id, user_id=context.user_id,
               operation=context.operation, model=model, route=route, attempt=attempt,
               status=status, http_status=status_code, elapsed_ms=max(0, elapsed_ms), **tokens)
    try:
        ensure_storage(context.db)
        with closing(sqlite3.connect(context.db, timeout=15)) as db:
            db.execute('INSERT INTO ai_usage_events (' + ','.join(row) + ') VALUES (' + ','.join('?' for _ in row) + ')', tuple(row.values()))
            db.commit()
    except (sqlite3.Error, OSError):
        # Monitoring storage must not turn an otherwise valid AI result into a failure.
        log.warning('AI usage record could not be saved; check database availability')


async def tracked_post(client, url, *, model, route, attempt=1, **kwargs):
    context = CONTEXT.get()
    started_at = utc_now()
    started = time.monotonic()
    response = None
    error = None
    try:
        response = await client.post(url, **kwargs)
        return response
    except BaseException as caught:
        error = caught
        raise
    finally:
        record(context, model=model, route=route, attempt=attempt,
               started_at=started_at, elapsed_ms=round((time.monotonic() - started) * 1000),
               response=response, error=error)


def period_bounds(period, now=None):
    today = (now or datetime.now(timezone.utc)).astimezone(KST).date()
    start = today if period == 'today' else today.replace(day=1) if period == 'month' else today - timedelta(days=29)
    start_dt = datetime.combine(start, datetime.min.time(), KST).astimezone(timezone.utc)
    end_dt = datetime.combine(today + timedelta(days=1), datetime.min.time(), KST).astimezone(timezone.utc)
    return start, today, start_dt.isoformat(), end_dt.isoformat()


def _blank():
    result = {key: 0 for key in (
        'requests', 'successful_requests', 'failed_requests', 'known_usage_requests',
        'unknown_usage_requests',
        'input_tokens', 'output_tokens', 'total_tokens', 'cached_input_tokens', 'reasoning_tokens')}
    return result


def _add(metric, row):
    metric['requests'] += 1
    metric['successful_requests' if row['status'] == 'success' else 'failed_requests'] += 1
    metric['known_usage_requests' if row['usage_known'] else 'unknown_usage_requests'] += 1
    if row['usage_known']:
        for key in ('input_tokens', 'output_tokens', 'total_tokens', 'cached_input_tokens', 'reasoning_tokens'):
            metric[key] += row[key]


def usage_report(path, period='month', now=None, users=None):
    ensure_storage(path)
    start, end, since, until = period_bounds(period, now)
    with closing(sqlite3.connect(path, timeout=15)) as db:
        db.row_factory = sqlite3.Row
        rows = [dict(row) for row in db.execute('SELECT * FROM ai_usage_events WHERE created_at >= ? AND created_at < ? ORDER BY created_at', (since, until))]
        first = db.execute('SELECT MIN(created_at) FROM ai_usage_events').fetchone()[0]
        started = json.loads(db.execute("SELECT payload FROM ai_usage_settings WHERE name='recording_started_at'").fetchone()[0])
        has_handovers = db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='handovers'").fetchone()
        names = {row[0]: json.loads(row[1]).get('handover', {}).get('name', '인수인계') for row in db.execute('SELECT id,payload FROM handovers')} if has_handovers else {}
    summary = _blank()
    daily = {(start + timedelta(days=i)).isoformat(): _blank() for i in range((end - start).days + 1)}
    user_names = {user['id']: user for user in users or []}
    models, features, handovers, user_totals = {}, {}, {}, {}
    for row in rows:
        day = datetime.fromisoformat(row['created_at']).astimezone(KST).date().isoformat()
        groups = [summary, daily[day], models.setdefault(row['model'], _blank()),
                  features.setdefault(row['operation'], _blank()), handovers.setdefault(row['handover_id'], _blank()),
                  user_totals.setdefault(row['user_id'], _blank())]
        for metric in groups:
            _add(metric, row)
    return {
        'period': period, 'timezone': 'Asia/Seoul', 'start_date': start.isoformat(), 'end_date': end.isoformat(),
        'recording_started_at': started, 'first_request_at': first,
        'summary': summary,
        'daily': [{'date': key, **value} for key, value in daily.items()],
        'models': [{'model': key, **value} for key, value in sorted(models.items(), key=lambda pair: -pair[1]['total_tokens'])],
        'features': [{'operation': key, 'label': OPERATIONS.get(key, OPERATIONS['other']), **value} for key, value in sorted(features.items(), key=lambda pair: -pair[1]['total_tokens'])],
        'handovers': [{'handover_id': key, 'name': names.get(key, '삭제된 인수인계') if key else '공통 작업', **value} for key, value in sorted(handovers.items(), key=lambda pair: -pair[1]['total_tokens'])],
        'users': [{
            'user_id': key,
            'name': '사용자 미확인' if key is None else user_names.get(key, {}).get('name', '등록되지 않은 사용자'),
            'department': user_names.get(key, {}).get('department', ''),
            **value,
        } for key, value in sorted(user_totals.items(), key=lambda pair: (-pair[1]['total_tokens'], pair[0] or ''))],
        'notes': [
            '기록 시작 이후 API가 반환한 사용량만 집계합니다. 이전 사용량은 복원하지 않습니다.',
            '사용량 미확인 호출은 토큰 합계에서 제외합니다. 재시도와 응답 후 검증에 실패한 호출도 포함합니다.',
            '캐시 입력 토큰과 추론 토큰은 각각 입력·출력 토큰에 포함된 수치이며 합계에 다시 더하지 않습니다.',
        ],
    }


def install(module):
    router = APIRouter(prefix='/api/admin')

    def admin(user=Depends(module.current_user)):
        if user.get('role') != 'admin':
            raise HTTPException(403, '관리자만 전체 AI 사용량을 확인할 수 있습니다.')
        return user

    @router.get('/ai-usage')
    def report(period: Literal['today', 'month', '30d'] = 'month', user=Depends(admin)):
        module.ensure_storage()
        return usage_report(module.DB, period, users=module.DEMO_USERS)

    module.app.include_router(router)
    module.app.add_middleware(UsageContextMiddleware, module=module)
