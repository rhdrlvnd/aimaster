import unittest
from collections import Counter
from datetime import date
from fastapi import HTTPException
from backend.scheduling import ScheduleSettings, ScheduleRow, OrderEntry, allocate_balanced, validate_rows

class BalancedTests(unittest.TestCase):
    def fixture(self, count=26):
        state={'items':[{'id':str(i)} for i in range(count)],'handover':{'start_date':'2026-10-21','end_date':'2026-10-30'}}
        settings=ScheduleSettings(start='2026-10-21',end='2026-10-30',unit='balanced',dependencies={'1':['0']})
        entries=[OrderEntry(item_id=str(i),reason='배치') for i in reversed(range(count))]
        return state,settings,entries

    def test_even_distribution_and_dependencies(self):
        state,settings,entries=self.fixture()
        rows=allocate_balanced(state,settings,entries,{},date(2026,10,21))
        counts=Counter(row['start'] for row in rows)
        self.assertEqual(len(counts),8)
        self.assertEqual(sorted(counts.values()),[3]*6+[4]*2)
        by={r['item_id']:r for r in rows}
        self.assertLessEqual(by['0']['start'],by['1']['start'])
        self.assertTrue(all(r['start_time'] is None for r in rows))

    def test_same_day_has_no_capacity_limit(self):
        state,settings,entries=self.fixture()
        settings.end=settings.start
        rows=allocate_balanced(state,settings,entries,{},settings.start)
        self.assertEqual(len(rows),26)
        self.assertEqual(len({r['start'] for r in rows}),1)

    def test_move_rejects_reversed_dependency(self):
        state,settings,entries=self.fixture(2)
        rows=[ScheduleRow(item_id='0',start='2026-10-22',end='2026-10-22'),ScheduleRow(item_id='1',start='2026-10-21',end='2026-10-21')]
        with self.assertRaises(HTTPException): validate_rows(state,settings,rows)

    def test_completed_task_preserved(self):
        state,settings,entries=self.fixture(2)
        fixed={'0':ScheduleRow(item_id='0',start='2026-10-21',end='2026-10-21').model_dump(mode='json')}
        rows=allocate_balanced(state,settings,entries,fixed,date(2026,10,22))
        self.assertEqual(rows[0],fixed['0'])
        self.assertEqual(rows[1]['start'],'2026-10-22')
