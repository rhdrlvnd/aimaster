import asyncio
import json
import time
import unittest
from datetime import datetime
from unittest.mock import AsyncMock, patch
from urllib.parse import parse_qs, urlparse
import httpx
from backend import app as m, google_store as store, google_tasks as tasks, calendar_api
from backend import test_features


def response(value, code=200):
    return httpx.Response(code, json=value)


class TaskTests(unittest.TestCase):
    login = test_features.FeatureTests.login
    state = test_features.FeatureTests.state
    features = test_features.FeatureTests.features
    post = test_features.FeatureTests.post
    draft = test_features.FeatureTests.draft
    confirm = test_features.FeatureTests.confirm
    tearDown = test_features.FeatureTests.tearDown
    def setUp(self):
        test_features.FeatureTests.setUp(self)
        calendar_api.TOKENS.clear()
        self.account = {'account_id': 'google-sub', 'access_token': 'private-test-access', 'refresh_token': 'private-test-refresh',
                        'expires_at': time.time()+3600, 'scope': calendar_api.SCOPES}
        self.http = AsyncMock()
        self.http.__aenter__.return_value = self.http

    def connected(self):
        self.confirm()
        self.login('demo-next')
        store.save_account('demo-next', self.account)

    def link(self, key, ls='todo', rs='needsAction'):
        store.save_link('demo-next', 'google-sub', self.state()['handover']['id'], key,
                        {'task_id': 'task-'+key, 'local_status': ls, 'remote_status': rs, 'status': 'synced'})

    def run_batch(self):
        with patch.object(tasks.httpx, 'AsyncClient', return_value=self.http):
            return asyncio.run(tasks.run_due(m, self.persist, datetime(2026,11,3,6,0,tzinfo=tasks.KST)))

    def persist(self, state, body, user):
        from backend.features import apply_progress
        apply_progress(state,body,user)

    def test_registration_repeat_updates_date_without_resetting_completion(self):
        self.connected()
        self.http.get.return_value=response({'items':[]})
        self.http.post.return_value=response({'id':'task-a','status':'needsAction'},201)
        with patch.object(tasks.httpx,'AsyncClient',return_value=self.http):
            result=self.post('/google/tasks',item_ids=['a'])
        self.assertEqual(result.status_code,200,result.text)
        self.assertEqual(result.json()['results'][0]['task_id'],'task-a')
        self.http.get.return_value=response({'items':[{'id':'task-a','status':'completed','etag':'v2'}]})
        self.http.patch.return_value=response({'id':'task-a','status':'completed'})
        with patch.object(tasks.httpx,'AsyncClient',return_value=self.http):
            result=self.post('/google/tasks',item_ids=['a'])
        self.assertEqual(result.status_code,200)
        self.assertEqual(self.http.post.await_count,1)
        self.assertNotIn('status',self.http.patch.call_args.kwargs['json'])
        self.assertEqual(self.http.patch.call_args.kwargs['headers']['If-Match'],'v2')

    def test_ambiguous_insert_recovers_exact_marker_without_duplicate(self):
        self.connected()
        self.http.get.return_value=response({'items':[]})
        self.http.post.side_effect=httpx.ReadTimeout('timeout')
        with patch.object(tasks.httpx,'AsyncClient',return_value=self.http):
            first=self.post('/google/tasks',item_ids=['a'])
        self.assertEqual(first.json()['results'][0]['status'],'failed')
        note=tasks.marker('demo-next','google-sub',self.state()['handover']['id'],'a')
        self.http.get.return_value=response({'items':[{'id':'recovered','status':'needsAction','notes':note}]})
        with patch.object(tasks.httpx,'AsyncClient',return_value=self.http):
            second=self.post('/google/tasks',item_ids=['a'])
        self.assertEqual(second.json()['results'][0]['task_id'],'recovered')
        self.assertEqual(self.http.post.await_count,1)

    def test_google_completed_chain_pulls_and_batch_runs_once(self):
        self.connected();self.link('a');self.link('b')
        self.http.get.return_value=response({'items':[{'id':'task-'+k,'status':'completed'} for k in ['a','b']]})
        self.assertTrue(self.run_batch())
        self.assertEqual([self.features()['progress'][k]['status'] for k in ['a','b']],['done','done'])
        self.assertFalse(self.run_batch())
        self.assertEqual(self.http.get.await_count,1)
        self.assertEqual(self.http.get.call_args.kwargs['params']['showHidden'],'true')

    def test_local_completion_is_pushed_only_by_daily_batch(self):
        self.connected();self.link('a')
        with patch.object(tasks.httpx,'AsyncClient',return_value=self.http):
            self.assertEqual(self.post('/progress',item_ids=['a'],status='done').status_code,200)
            self.http.patch.assert_not_called()
        self.http.get.return_value=response({'items':[{'id':'task-a','status':'needsAction','etag':'v1'}]})
        self.http.patch.return_value=response({'id':'task-a','status':'completed'})
        self.run_batch()
        self.assertEqual(self.http.patch.call_args.kwargs['json'],{'status':'completed'})
        self.assertEqual(self.features()['google_tasks']['items'][0]['status'],'synced')

    def test_undo_chain_from_google(self):
        self.connected();self.post('/progress',item_ids=['a','b'],status='done')
        self.link('a','done','completed');self.link('b','done','completed')
        self.http.get.return_value=response({'items':[{'id':'task-'+k,'status':'needsAction'} for k in ['a','b']]})
        self.run_batch()
        self.assertEqual([self.features()['progress'][k]['status'] for k in ['a','b']],['todo','todo'])

    def test_prerequisite_completion_guard(self):
        self.connected();self.link('a');self.link('b')
        self.http.get.return_value=response({'items':[{'id':'task-a','status':'needsAction'},{'id':'task-b','status':'completed'}]})
        self.run_batch()
        self.assertNotIn('b',self.features()['progress'])
        warning=next(v for v in self.features()['google_tasks']['items'] if v['item_id']=='b')
        self.assertEqual(warning['status'],'attention')

    def test_predecessor_undo_blocked_if_completed_successor_remains(self):
        self.connected();self.post('/progress',item_ids=['a','b'],status='done')
        self.link('a','done','completed');self.link('b','done','completed')
        self.http.get.return_value=response({'items':[{'id':'task-a','status':'needsAction'},{'id':'task-b','status':'completed'}]})
        self.run_batch()
        self.assertEqual(self.features()['progress']['a']['status'],'done')

    def test_conflict_and_deleted_task_leave_local_state(self):
        self.connected();self.link('a');self.link('b')
        self.post('/progress',item_ids=['a'],status='doing')
        self.http.get.return_value=response({'items':[{'id':'task-a','status':'completed'},{'id':'task-b','deleted':True}]})
        self.run_batch()
        self.assertEqual(self.features()['progress']['a']['status'],'doing')
        self.assertEqual([v['status'] for v in self.features()['google_tasks']['items']],['attention','attention'])
        self.http.patch.assert_not_called()

    def test_account_isolation_and_encrypted_restart_persistence(self):
        self.connected();self.link('a')
        with store.database() as db:
            secret=db.execute('SELECT secret FROM google_accounts').fetchone()[0]
        self.assertNotIn('private-test',secret)
        calendar_api.TOKENS.clear()
        self.assertTrue(self.features()['calendar']['connected'])
        store.save_account('demo-next',{**self.account,'account_id':'other-google'})
        self.assertEqual(self.features()['google_tasks']['linked_count'],0)
        self.run_batch();self.http.get.assert_not_called()

    def test_stale_revision_and_owner_cannot_register(self):
        self.connected()
        self.assertEqual(self.client.post(self.prefix+'/google/tasks',json={'revision':0,'item_ids':['a']}).status_code,409)
        self.login('demo-dev')
        self.assertEqual(self.post('/google/tasks',item_ids=['a']).status_code,403)

    def test_old_calendar_consent_requires_reconnect(self):
        self.connected()
        store.save_account('demo-next',{**self.account,'scope':'https://www.googleapis.com/auth/calendar.events'})
        self.assertFalse(self.features()['calendar']['connected'])
        self.assertTrue(self.features()['calendar']['needs_reconnect'])
        self.assertEqual(self.post('/google/tasks',item_ids=['a']).status_code,409)

    def test_pagination_and_partial_registration_failure(self):
        self.connected()
        self.http.get.side_effect=[response({'items':[],'nextPageToken':'next'}),response({'items':[]})]
        self.http.post.side_effect=[response({'id':'task-a','status':'needsAction'},201),response({},403)]
        with patch.object(tasks.httpx,'AsyncClient',return_value=self.http):
            result=self.post('/google/tasks',item_ids=['a','b'])
        self.assertEqual([r['status'] for r in result.json()['results']],['success','failed'])
        self.assertEqual(self.http.get.await_count,2)

    def test_legacy_event_cleanup_only_after_task_saved(self):
        self.connected()
        self.http.get.side_effect=[response({'items':[]}),response({'extendedProperties':{'private':{'handover_id':self.state()['handover']['id'],'item_id':'a'}}})]
        self.http.post.return_value=response({'id':'task-a','status':'needsAction'},201)
        self.http.delete.return_value=response({},204)
        with patch.object(tasks.httpx,'AsyncClient',return_value=self.http):
            result=self.post('/google/tasks',item_ids=['a'],replace_events=True)
        self.assertEqual(result.json()['results'][0]['status'],'success')
        self.http.delete.assert_awaited_once()

    def test_oauth_tasks_consent_saved_with_account_identity(self):
        self.login('demo-next')
        with patch.object(calendar_api,'config',return_value=('client','secret','http://testserver/api/calendar/callback')):
            connect=self.client.post('/api/calendar/connect')
            query=parse_qs(urlparse(connect.json()['url']).query)
            self.assertIn(tasks.TASKS_SCOPE,query['scope'][0])
            self.http.post.return_value=response({'access_token':'a','refresh_token':'r','scope':calendar_api.SCOPES})
            self.http.get.return_value=response({'sub':'google-id'})
            with patch.object(calendar_api.httpx,'AsyncClient',return_value=self.http):
                result=self.client.get('/api/calendar/callback',params={'state':query['state'][0],'code':'test'},follow_redirects=False)
        self.assertEqual(result.status_code,307,result.text)
        self.assertEqual(store.account('demo-next')['account_id'],'google-id')

    def test_daily_boundary_and_lease(self):
        self.connected()
        self.assertFalse(asyncio.run(tasks.run_due(m,self.persist,datetime(2026,11,3,5,59,tzinfo=tasks.KST))))
        lease=store.acquire('google-daily-batch')
        self.assertFalse(self.run_batch())
        store.release('google-daily-batch',lease)
        self.assertTrue(self.run_batch())
        self.assertEqual(tasks.next_run(datetime(2026,11,3,6,0,tzinfo=tasks.KST)).day,4)

    def test_local_undo_push_and_remote_change_precondition(self):
        self.connected();self.post('/progress',item_ids=['a'],status='done')
        self.link('a','done','completed');self.post('/progress',item_ids=['a'],status='todo')
        self.http.get.return_value=response({'items':[{'id':'task-a','status':'completed','etag':'v2'}]})
        self.http.patch.return_value=response({},412)
        self.run_batch()
        self.assertEqual(self.http.patch.call_args.kwargs['json'],{'status':'needsAction','completed':None})
        self.assertEqual(self.features()['progress']['a']['status'],'todo')
        link=store.links('demo-next','google-sub',self.state()['handover']['id'])['a']
        self.assertEqual(link['remote_status'],'completed')
        self.assertEqual(link['status'],'attention')

    def test_stale_local_state_during_google_read_is_not_overwritten(self):
        self.connected();self.link('a')
        async def remote_read(*args,**kwargs):
            with m.LOCK:
                state=m.read_state();state['progress']={'a':{'status':'doing'}};m.write_state(state)
            return response({'items':[{'id':'task-a','status':'completed'}]})
        self.http.get.side_effect=remote_read
        self.run_batch()
        self.assertEqual(self.features()['progress']['a']['status'],'doing')
        self.assertEqual(self.features()['google_tasks']['items'][0]['status'],'error')

    def test_legacy_event_with_wrong_owner_is_never_deleted(self):
        self.connected()
        self.http.get.side_effect=[response({'items':[]}),response({'extendedProperties':{'private':{'handover_id':'another','item_id':'a'}}})]
        self.http.post.return_value=response({'id':'task-a','status':'needsAction'},201)
        with patch.object(tasks.httpx,'AsyncClient',return_value=self.http):
            result=self.post('/google/tasks',item_ids=['a'],replace_events=True)
        self.assertEqual(result.json()['results'][0]['status'],'failed')
        self.http.delete.assert_not_called()
        self.assertEqual(self.features()['google_tasks']['linked_count'],1)

    def test_restart_keeps_batch_completion_record_and_oauth_refresh(self):
        self.connected();self.link('a')
        store.save_account('demo-next',{**self.account,'expires_at':0})
        self.http.post.return_value=response({'access_token':'refreshed','expires_in':3600})
        self.http.get.return_value=response({'items':[{'id':'task-a','status':'needsAction'}]})
        self.run_batch()
        self.assertEqual(store.account('demo-next')['access_token'],'refreshed')
        calendar_api.TOKENS.clear()
        self.assertFalse(self.run_batch())
        self.assertEqual(self.http.post.await_count,1)

    def test_no_task_recreation_after_google_delete(self):
        self.connected();self.link('a')
        self.http.get.return_value=response({'items':[{'id':'task-a','deleted':True}]})
        with patch.object(tasks.httpx,'AsyncClient',return_value=self.http):
            result=self.post('/google/tasks',item_ids=['a'])
        self.assertEqual(result.json()['results'][0]['status'],'failed')
        self.http.post.assert_not_called()
