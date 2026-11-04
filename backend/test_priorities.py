"""Priority wording changes must not invalidate reviewed user data."""
import asyncio
import copy
import hashlib
import json
import sqlite3
import tempfile
import unittest
from contextlib import closing
from datetime import date
from io import BytesIO
from pathlib import Path
from unittest.mock import AsyncMock, patch

from docx import Document
from pydantic import ValidationError
from backend import app, admin_dashboard, google_tasks, scheduling
from backend.exporting import build_docx
from backend.priorities import normalize_state_priorities


def fixture():
    state = {
        'revision': 7, 'status': 'approved', 'documents': [],
        'handover': {
            'id': 'priority-test', 'name': '인수인계', 'owner': '전임자',
            'owner_id': 'demo-dev', 'successor': '후임자', 'successor_id': 'demo-next',
            'start_date': '2030-11-04', 'end_date': '2030-11-15',
        },
        'items': [
            {'id': key, 'title': title, 'description': '업무를 확인한다.',
             'category': '운영', 'priority': priority, 'reviewed': True,
             'origin': 'manual', 'evidence': [], 'dependencies': []}
            for key, title, priority in [
                ('urgent', '장애 대응', '높음'),
                ('normal', '정기 점검', '보통'),
                ('relaxed', '과거 기록 확인', '낮음'),
            ]
        ],
        'progress': {'urgent': {'status': 'done'}},
    }
    # This is exactly the hash written by the implementation before renaming.
    old_hash = hashlib.sha256(json.dumps(
        {'items': state['items'], 'period': state['handover']},
        sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    state['schedule'] = {
        'fingerprint': old_hash, 'confirmed_at': '2030-11-01',
        'confirmed': [{'item_id': item['id'], 'start': '2030-11-04', 'end': '2030-11-04'} for item in state['items']],
        'draft': {'fingerprint': old_hash},
    }
    state['signature'] = {'fingerprint': old_hash, 'name': '전임자', 'signed_at': '2030-11-01'}
    return state


class PriorityTests(unittest.TestCase):
    def test_ai_schema_only_accepts_new_priorities(self):
        item = fixture()['items'][0]
        for priority in ('긴급', '보통', '여유'):
            self.assertEqual(app.Item.model_validate({**item, 'priority': priority}).priority, priority)
        for priority in ('높음', '낮음', '최상', ''):
            with self.assertRaises(ValidationError):
                app.Item.model_validate({**item, 'priority': priority})

    def test_review_accepts_legacy_browser_values_but_rejects_unknown(self):
        item = fixture()['items'][0]
        for old, new in [('높음', '긴급'), ('보통', '보통'), ('낮음', '여유')]:
            self.assertEqual(app.ReviewItem.model_validate({**item, 'priority': old}).priority, new)
        with self.assertRaises(ValidationError):
            app.ReviewItem.model_validate({**item, 'priority': '최상'})

    def test_renaming_keeps_historical_schedule_and_signature_hashes(self):
        legacy = fixture()
        current = normalize_state_priorities(copy.deepcopy(legacy))
        original_hash = legacy['schedule']['fingerprint']
        self.assertEqual(scheduling.fingerprint(legacy), original_hash)
        self.assertEqual(scheduling.fingerprint(current), original_hash)
        self.assertEqual(current['signature']['fingerprint'], original_hash)
        self.assertEqual(current['progress'], legacy['progress'])
        for state in (legacy, current):
            self.assertTrue(admin_dashboard.summarize(state, date(2030, 11, 4))['schedule_current'])
            google_tasks.check_state(state, 'demo-next')

    def test_real_edits_and_stale_hashes_remain_invalid(self):
        for change in ('title', 'priority', 'period'):
            state = normalize_state_priorities(fixture())
            if change == 'period':
                state['handover']['end_date'] = '2030-11-20'
            else:
                state['items'][0][change] = '수정한 업무' if change == 'title' else '보통'
            self.assertNotEqual(scheduling.fingerprint(state), state['schedule']['fingerprint'])
            self.assertFalse(admin_dashboard.summarize(state, date(2030, 11, 4))['schedule_current'])
        state = fixture()
        state['schedule']['fingerprint'] = 'already-stale'
        normalize_state_priorities(state)
        self.assertNotEqual(scheduling.fingerprint(state), state['schedule']['fingerprint'])

    def test_read_maps_labels_without_writing_or_bumping_revision(self):
        state = fixture()
        payload = json.dumps(state, ensure_ascii=False)
        with tempfile.TemporaryDirectory() as directory:
            db_path = Path(directory) / 'state.sqlite3'
            with closing(sqlite3.connect(db_path)) as db:
                db.execute('CREATE TABLE handovers (id TEXT PRIMARY KEY, payload TEXT NOT NULL)')
                db.execute('INSERT INTO handovers VALUES (?, ?)', (state['handover']['id'], payload))
                db.commit()
            token = app.HANDOVER_ID.set(state['handover']['id'])
            try:
                with patch.object(app, 'DB', db_path):
                    result = app.read_state()
                    self.assertEqual([item['priority'] for item in result['items']], ['긴급', '보통', '여유'])
                    self.assertEqual(result['revision'], 7)
                    self.assertEqual(result['schedule'], state['schedule'])
                    self.assertEqual(result['signature'], state['signature'])
                    self.assertEqual(result['progress'], state['progress'])
                with closing(sqlite3.connect(db_path)) as db:
                    self.assertEqual(db.execute('SELECT payload FROM handovers').fetchone()[0], payload)
            finally:
                app.HANDOVER_ID.reset(token)

    def test_export_uses_new_labels_for_both_stored_formats(self):
        legacy = fixture()
        for state in (legacy, normalize_state_priorities(copy.deepcopy(legacy))):
            text = '\n'.join(p.text for p in Document(BytesIO(build_docx(state, state['signature']))).paragraphs)
            self.assertIn('중요도: 긴급', text)
            self.assertIn('중요도: 보통', text)
            self.assertIn('중요도: 여유', text)
            self.assertNotIn('중요도: 높음', text)
            self.assertNotIn('중요도: 낮음', text)

    def test_urgent_prerequisite_is_promoted_without_changing_labels(self):
        state = fixture()
        settings = scheduling.ScheduleSettings(start='2030-11-04', end='2030-11-15', unit='balanced', dependencies={'urgent': ['relaxed']})
        entries = [scheduling.OrderEntry(item_id=key, reason='원문 기준') for key in ('normal', 'urgent', 'relaxed')]
        ordered = scheduling.prioritize_entries(state, settings, entries, {})
        self.assertEqual([entry.item_id for entry in ordered], ['relaxed', 'urgent', 'normal'])
        self.assertEqual(state['items'][2]['priority'], '낮음')
        fixed = {'relaxed': scheduling.ScheduleRow(item_id='relaxed', start='2030-11-04', end='2030-11-04').model_dump(mode='json')}
        ordered = scheduling.prioritize_entries(state, settings, entries, fixed)
        rows = scheduling.allocate_balanced(state, settings, ordered, fixed, date(2030, 11, 5))
        self.assertEqual(rows[0], fixed['relaxed'])
        self.assertEqual([row['item_id'] for row in rows], ['relaxed', 'urgent', 'normal'])

    def test_planner_sees_new_criteria_and_keeps_balanced_dates(self):
        state = fixture()
        state.pop('schedule')
        state['progress'] = {}
        settings = scheduling.ScheduleSettings(start='2030-11-04', end='2030-11-15', unit='balanced')
        response = {'items': [{'item_id': key, 'reason': '업무 맥락'} for key in ('relaxed', 'normal', 'urgent')]}
        with patch.object(scheduling, 'json_call', AsyncMock(return_value=response)) as ai:
            rows = asyncio.run(scheduling.propose(state, settings, False, lambda *_: None))
        self.assertEqual([row['item_id'] for row in rows], ['urgent', 'normal', 'relaxed'])
        self.assertEqual(rows[0]['start'], '2030-11-04')
        self.assertEqual(rows[-1]['start'], '2030-11-15')
        prompt, payload = ai.call_args.args[1:]
        self.assertIn('기간 절반 이내', prompt)
        self.assertIn('초반에 반드시', prompt)
        self.assertEqual([item['priority'] for item in payload['items']], ['긴급', '보통', '여유'])


if __name__ == '__main__':
    unittest.main()
