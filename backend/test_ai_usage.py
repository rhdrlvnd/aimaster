import asyncio
import json
import sqlite3
import tempfile
import unittest
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import httpx
from fastapi.testclient import TestClient

from backend import ai_usage as usage, ai_transport, agents, app as m, rag


def response(status=200, *, incoming=1000, outgoing=100, cached=200, reasoning=20):
    return httpx.Response(status, json={
        'usage': {'prompt_tokens': incoming, 'completion_tokens': outgoing,
                  'total_tokens': incoming + outgoing,
                  'prompt_tokens_details': {'cached_tokens': cached},
                  'completion_tokens_details': {'reasoning_tokens': reasoning}},
        'choices': [{'finish_reason': 'stop', 'message': {'content': '{}'}}],
    })


def rows(path):
    with closing(sqlite3.connect(path)) as db:
        db.row_factory = sqlite3.Row
        return [dict(row) for row in db.execute('SELECT * FROM ai_usage_events ORDER BY rowid')]


class UsageTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / 'usage.sqlite3'
        usage.ensure_storage(self.path)
        self.context = usage.UsageContext(self.path, 'handover-a', 'user-a', 'qa')
        self.token = usage.CONTEXT.set(self.context)

    def tearDown(self):
        usage.CONTEXT.reset(self.token)
        self.temp.cleanup()

    async def test_one_event_per_actual_request_and_no_sensitive_content(self):
        client = AsyncMock()
        client.__aenter__.return_value = client
        client.post.return_value = response()
        with patch.dict(m.os.environ, {'LLM_API_KEY': 'secret-key', 'LLM_BASE_URL': 'https://example.invalid'}), patch.object(rag.httpx, 'AsyncClient', return_value=client):
            await agents.json_call('test role', 'secret-system', {'private_document': 'PRIVATE SOURCE'})
        ledger = rows(self.path)
        self.assertEqual(len(ledger), 1)
        self.assertEqual(ledger[0]['input_tokens'], 1000)
        self.assertEqual(ledger[0]['output_tokens'], 100)
        self.assertEqual(ledger[0]['total_tokens'], 1100)
        self.assertEqual(ledger[0]['cached_input_tokens'], 200)
        self.assertEqual(ledger[0]['reasoning_tokens'], 20)
        self.assertEqual(ledger[0]['handover_id'], 'handover-a')
        self.assertNotIn('secret', json.dumps(ledger))
        self.assertNotIn('PRIVATE SOURCE', json.dumps(ledger))

    async def test_invalid_output_still_accounts_reported_tokens(self):
        client = AsyncMock()
        client.__aenter__.return_value = client
        value = response().json()
        value['choices'][0]['finish_reason'] = 'length'
        client.post.return_value = httpx.Response(200, json=value)
        with patch.dict(m.os.environ, {'LLM_API_KEY': 'test', 'LLM_BASE_URL': 'https://example.invalid'}), patch.object(rag.httpx, 'AsyncClient', return_value=client):
            with self.assertRaises(m.HTTPException):
                await agents.json_call('test role', 'prompt', {})
        self.assertEqual(rows(self.path)[0]['total_tokens'], 1100)

    async def test_retry_records_each_attempt_without_inventing_failed_usage(self):
        client = AsyncMock()
        client.post.side_effect = [httpx.Response(502, json={'error': 'upstream'}), response()]
        with patch.object(ai_transport.asyncio, 'sleep', AsyncMock()):
            await ai_transport.post(client, 'https://example.invalid', label='writer', json={'model': 'test-model'})
        ledger = rows(self.path)
        self.assertEqual([r['attempt'] for r in ledger], [1, 2])
        self.assertEqual([r['status'] for r in ledger], ['http_error', 'success'])
        self.assertIsNone(ledger[0]['total_tokens'])
        self.assertEqual(ledger[0]['usage_known'], 0)
        self.assertEqual(ledger[1]['total_tokens'], 1100)

    async def test_missing_usage_timeout_and_cancellation_are_unknown(self):
        client = AsyncMock()
        client.post.side_effect = [httpx.Response(200, json={'choices': []}), httpx.ReadTimeout('private request'), asyncio.CancelledError()]
        await usage.tracked_post(client, 'https://example.invalid', model='test', route='chat/completions')
        with self.assertRaises(httpx.ReadTimeout):
            await usage.tracked_post(client, 'https://example.invalid', model='test', route='chat/completions')
        with self.assertRaises(asyncio.CancelledError):
            await usage.tracked_post(client, 'https://example.invalid', model='test', route='chat/completions')
        ledger = rows(self.path)
        self.assertEqual([r['status'] for r in ledger], ['success', 'transport_error', 'cancelled'])
        self.assertTrue(all(r['usage_known'] == 0 and r['total_tokens'] is None for r in ledger))
        report = usage.usage_report(self.path)
        self.assertEqual(report['summary']['unknown_usage_requests'], 3)
        self.assertEqual(report['summary']['known_usage_requests'], 0)

    async def test_non_json_response_is_recorded_without_breaking_transport(self):
        client = AsyncMock()
        client.post.return_value = httpx.Response(502, content=b'<html>proxy failure</html>')
        result = await usage.tracked_post(client, 'https://example.invalid', model='test', route='chat/completions')
        self.assertEqual(result.status_code, 502)
        self.assertEqual(rows(self.path)[0]['usage_known'], 0)

    async def test_concurrent_streams_and_nested_tasks_keep_attribution(self):
        module = SimpleNamespace(DB=self.path, SESSIONS={'cookie-a': 'user-a', 'cookie-b': 'user-b'})
        ids = ['00000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-000000000002']

        async def application(scope, receive, send):
            captured = usage.CONTEXT.get()
            await send({'type': 'http.response.start', 'status': 200, 'headers': []})

            async def streamed_work():
                await asyncio.sleep(0)
                self.assertEqual(await asyncio.to_thread(usage.CONTEXT.get), captured)

                async def nested():
                    await asyncio.sleep(0)
                    client = AsyncMock()
                    client.post.return_value = response()
                    await usage.tracked_post(client, 'https://example.invalid', model='test', route='chat/completions')

                await asyncio.gather(asyncio.create_task(nested()), asyncio.create_task(nested()))

            await asyncio.create_task(streamed_work())
            await send({'type': 'http.response.body', 'body': b'done'})

        middleware = usage.UsageContextMiddleware(application, module)

        async def run(index, suffix):
            scope = {'type': 'http', 'method': 'POST', 'scheme': 'http',
                     'path': '/api/handovers/' + ids[index] + suffix, 'query_string': b'',
                     'headers': [(b'cookie', ('handover_session=cookie-' + 'ab'[index]).encode())]}
            await middleware(scope, AsyncMock(), AsyncMock())

        await asyncio.gather(run(0, '/generate/stream'), run(1, '/qa/stream'))
        ledger = rows(self.path)
        self.assertEqual(len(ledger), 4)
        for index in range(2):
            own = [r for r in ledger if r['handover_id'] == ids[index]]
            self.assertEqual(len(own), 2)
            self.assertTrue(all(r['user_id'] == 'user-' + 'ab'[index] for r in own))
            self.assertTrue(all(r['operation'] == ('checklist', 'qa')[index] for r in own))
        self.assertEqual(usage.CONTEXT.get(), self.context)

    async def test_storage_failure_does_not_destroy_ai_response(self):
        client = AsyncMock()
        client.post.return_value = response()
        with patch.object(usage, 'ensure_storage', side_effect=sqlite3.OperationalError('locked')):
            result = await usage.tracked_post(client, 'https://example.invalid', model='test', route='chat/completions')
        self.assertEqual(result.status_code, 200)


class UsageReportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / 'usage.sqlite3'
        self.context = usage.UsageContext(self.path, 'handover-a', 'user-a', 'document_analysis')
        usage.ensure_storage(self.path)

    def tearDown(self):
        self.temp.cleanup()

    def add(self, model='chat-model', timestamp='2026-11-02T15:00:00+00:00', result=None, route='chat/completions'):
        usage.record(self.context, model=model, route=route, attempt=1, started_at=timestamp,
                     elapsed_ms=15, response=result if result is not None else response())

    def test_chat_and_embedding_usage_formats(self):
        chat = usage.normalize_usage({'usage': {'input_tokens': 10, 'output_tokens': 3, 'input_tokens_details': {'cached_tokens': 4}, 'output_tokens_details': {'reasoning_tokens': 2}}}, 'chat/completions')
        self.assertEqual(chat['total_tokens'], 13)
        embedding = usage.normalize_usage({'usage': {'prompt_tokens': 15, 'total_tokens': 15}}, 'embeddings')
        self.assertEqual(embedding['input_tokens'], 15)
        self.assertEqual(embedding['output_tokens'], 0)
        for malformed in ({}, {'prompt_tokens': -1, 'completion_tokens': 1}, {'prompt_tokens': True, 'completion_tokens': 1}, {'prompt_tokens': 5, 'completion_tokens': 1, 'prompt_tokens_details': {'cached_tokens': 6}}, {'prompt_tokens': 100, 'completion_tokens': 30, 'total_tokens': 20}):
            self.assertEqual(usage.normalize_usage({'usage': malformed}, 'chat/completions')['usage_known'], 0)

    def test_all_application_ai_entry_points_have_a_feature(self):
        prefix = '/api/handovers/00000000-0000-0000-0000-000000000001'
        for suffix, expected in [
            ('/documents', 'document_analysis'), ('/documents/stream', 'document_analysis'),
            ('/documents/document-id/analyze/stream', 'document_analysis'),
            ('/generate', 'checklist'), ('/generate/stream', 'checklist'),
            ('/checklist/dependencies/stream', 'dependencies'),
            ('/schedule/generate/stream', 'schedule'), ('/qa/stream', 'qa'),
        ]:
            with self.subTest(path=suffix):
                self.assertEqual(usage.operation_for_path(prefix + suffix), expected)

    def test_cache_and_reasoning_are_not_added_twice(self):
        self.add()
        report = usage.usage_report(self.path, 'today', datetime(2026, 11, 3, tzinfo=timezone.utc))
        self.assertEqual(report['summary']['total_tokens'], 1100)
        self.assertEqual(report['summary']['reasoning_tokens'], 20)
        self.assertEqual(report['summary']['cached_input_tokens'], 200)
        self.assertEqual(report['features'][0]['operation'], 'document_analysis')
        self.assertEqual(report['handovers'][0]['handover_id'], 'handover-a')
        self.assertEqual(report['models'][0]['model'], 'chat-model')

    def test_unknown_usage_is_excluded_and_counted_separately(self):
        self.add()
        self.add(model='other-model')
        self.add(model='chat-model', result=httpx.Response(504, json={'error': 'timeout'}))
        report = usage.usage_report(self.path, 'month', datetime(2026, 11, 3, tzinfo=timezone.utc))
        self.assertEqual(report['summary']['unknown_usage_requests'], 1)
        self.assertEqual(report['summary']['known_usage_requests'], 2)
        self.assertEqual(report['summary']['total_tokens'], 2200)
        self.assertEqual({row['model'] for row in report['models']}, {'chat-model', 'other-model'})

    def test_korean_day_and_month_boundaries_and_zero_filled_days(self):
        self.add(timestamp='2026-10-31T14:59:59+00:00')  # Oct 31 KST
        self.add(timestamp='2026-10-31T15:00:00+00:00')  # Nov 1 KST
        self.add(timestamp='2026-11-02T14:59:59+00:00')  # Nov 2 KST
        self.add(timestamp='2026-11-02T15:00:00+00:00')  # Nov 3 KST
        now = datetime(2026, 11, 3, 1, tzinfo=timezone.utc)
        self.assertEqual(usage.usage_report(self.path, 'today', now)['summary']['requests'], 1)
        month = usage.usage_report(self.path, 'month', now)
        self.assertEqual(month['summary']['requests'], 3)
        self.assertEqual([d['date'] for d in month['daily']], ['2026-11-01', '2026-11-02', '2026-11-03'])
        recent = usage.usage_report(self.path, '30d', now)
        self.assertEqual(len(recent['daily']), 30)
        self.assertEqual(recent['summary']['requests'], 4)
        self.assertEqual(recent['start_date'], '2026-10-05')

    def test_users_group_by_id_with_same_names_unknown_and_removed_users(self):
        users = [
            {'id': 'user-a', 'name': '김담당', 'department': '개발팀'},
            {'id': 'user-b', 'name': '김담당', 'department': '인사팀'},
            {'id': 'unused', 'name': '미사용자', 'department': '재무팀'},
        ]
        # Insert equal-token users in reverse ID order to check stable sorting.
        for user_id in ('user-b', 'user-a', None, 'removed-user'):
            self.context = usage.UsageContext(self.path, 'handover-a', user_id, 'qa')
            self.add()
        self.add(result=httpx.Response(502, json={'error': 'unavailable'}))
        report = usage.usage_report(self.path, 'month', datetime(2026, 11, 3, tzinfo=timezone.utc), users=users)
        self.assertEqual([row['user_id'] for row in report['users']], [None, 'removed-user', 'user-a', 'user-b'])
        by_id = {row['user_id']: row for row in report['users']}
        self.assertEqual(by_id['user-a']['name'], '김담당')
        self.assertEqual(by_id['user-b']['name'], '김담당')
        self.assertEqual(by_id['user-a']['department'], '개발팀')
        self.assertEqual(by_id['user-b']['department'], '인사팀')
        self.assertEqual(by_id[None]['name'], '사용자 미확인')
        self.assertEqual(by_id['removed-user']['name'], '등록되지 않은 사용자')
        self.assertEqual(by_id['removed-user']['department'], '')
        self.assertEqual(by_id['removed-user']['unknown_usage_requests'], 1)
        self.assertNotIn('unused', by_id)
        for field, total in report['summary'].items():
            self.assertEqual(sum(row[field] for row in report['users']), total, field)
        # Optional user lookup cannot drop stored usage when metadata is unavailable.
        without_names = usage.usage_report(self.path, 'month', datetime(2026, 11, 3, tzinfo=timezone.utc))
        self.assertEqual(without_names['summary'], report['summary'])
        self.assertEqual(len(without_names['users']), 4)

    def test_users_include_only_selected_period_and_sort_by_total_tokens(self):
        self.context = usage.UsageContext(self.path, 'handover-a', 'prior-month', 'qa')
        self.add(timestamp='2026-10-31T14:59:59+00:00')
        self.context = usage.UsageContext(self.path, 'handover-a', 'month-user', 'qa')
        self.add(timestamp='2026-10-31T15:00:00+00:00')
        self.context = usage.UsageContext(self.path, 'handover-b', 'today-user', 'qa')
        self.add(timestamp='2026-11-02T15:00:00+00:00', result=response(incoming=2000))
        now = datetime(2026, 11, 3, tzinfo=timezone.utc)
        month = usage.usage_report(self.path, 'month', now)
        today = usage.usage_report(self.path, 'today', now)
        self.assertEqual([row['user_id'] for row in month['users']], ['today-user', 'month-user'])
        self.assertEqual([row['user_id'] for row in today['users']], ['today-user'])
        self.assertEqual(today['users'][0]['total_tokens'], today['summary']['total_tokens'])

class UsageApiTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.old = m.DB
        m.DB = Path(self.temp.name) / 'test.sqlite3'
        self.client = TestClient(m.app)

    def tearDown(self):
        self.client.close()
        m.DB = self.old
        self.temp.cleanup()

    def login(self, user):
        self.client.post('/api/demo/session', json={'user_id': user}).raise_for_status()

    def test_only_admin_can_read_and_period_is_validated(self):
        self.assertEqual(self.client.get('/api/admin/ai-usage').status_code, 401)
        for user in ('demo-dev', 'demo-next'):
            self.login(user)
            self.assertEqual(self.client.get('/api/admin/ai-usage').status_code, 403)
        self.login('demo-admin')
        initial = self.client.get('/api/admin/ai-usage').json()
        self.assertEqual(initial['summary']['requests'], 0)
        self.assertEqual(initial['users'], [])
        self.assertIsNone(initial['first_request_at'])
        self.assertTrue(initial['recording_started_at'])
        self.assertEqual(self.client.get('/api/admin/ai-usage?period=year').status_code, 422)
        self.assertNotIn('pricing', initial)
        self.assertEqual(self.client.get('/api/admin/ai-pricing').status_code, 404)

    def test_real_stream_route_preserves_user_handover_and_operation(self):
        self.login('demo-dev')
        r = self.client.post('/api/handovers', json=dict(name='AI 집계 시험', scope='문서 분석', owner='김개발', successor='이후임', start_date='2026-11-01', end_date='2026-11-30'))
        self.assertEqual(r.status_code, 201, r.text)
        handover_id = r.json()['id']

        async def prepare(doc, content, root, report):
            # Real rag.request transport inside the application's background stream task.
            await rag.request('embedding-test', 'embeddings', {'model': 'embedding-test', 'input': ['private source']})
            report('store', '완료')
            return {'status': 'ready', 'chunk_count': 1, 'vector_count': 1}

        client = AsyncMock()
        client.__aenter__.return_value = client
        client.post.return_value = httpx.Response(200, json={'usage': {'prompt_tokens': 12, 'total_tokens': 12}, 'data': []})
        with patch.dict(m.os.environ, {'LLM_API_KEY': 'test', 'LLM_BASE_URL': 'https://example.invalid'}), patch.object(rag, 'prepare', prepare), patch.object(rag.httpx, 'AsyncClient', return_value=client):
            result = self.client.post('/api/handovers/' + handover_id + '/documents/stream', files={'file': ('manual.txt', b'private source')})
        self.assertEqual(json.loads(result.text.splitlines()[-1])['stage'], 'done', result.text)
        ledger = rows(m.DB)
        self.assertEqual(len(ledger), 1)
        self.assertEqual(ledger[0]['handover_id'], handover_id)
        self.assertEqual(ledger[0]['user_id'], 'demo-dev')
        self.assertEqual(ledger[0]['operation'], 'document_analysis')
        self.assertEqual(ledger[0]['route'], 'embeddings')
        self.assertEqual(ledger[0]['output_tokens'], 0)
        self.login('demo-admin')
        summary = self.client.get('/api/admin/ai-usage').json()
        self.assertEqual(summary['handovers'][0]['name'], 'AI 집계 시험')
        self.assertEqual(summary['summary']['total_tokens'], 12)
        self.assertEqual(summary['users'][0]['user_id'], 'demo-dev')
        self.assertEqual(summary['users'][0]['name'], '김개발')
        self.assertEqual(summary['users'][0]['department'], '개발팀')
        self.assertEqual(summary['users'][0]['total_tokens'], 12)


if __name__ == '__main__':
    unittest.main()
