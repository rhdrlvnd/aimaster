"""Add empty demo handovers without altering uploaded documents or checklists."""
import json
import sqlite3
import uuid
from contextlib import closing
from backend import app as mod


def seed():
    mod.ensure_storage()
    samples = [
        ('주문 서비스 운영 인수인계', '주문 배치와 운영 점검', 'demo-dev', 'demo-next'),
        ('입퇴사·근태 업무 인수인계', '입퇴사 처리와 월별 근태 마감', 'demo-hr', 'demo-finance'),
        ('월 결산 업무 인수인계', '월 결산 자료 취합과 비용 정산', 'demo-finance', 'demo-legal'),
        ('계약 검토 업무 인수인계', '계약 검토 요청과 법무 검토 이력 관리', 'demo-legal', 'demo-hr'),
    ]
    users = {u['id']:u for u in mod.DEMO_USERS}
    with closing(sqlite3.connect(mod.DB)) as db:
        for index, (name, scope, owner, successor) in enumerate(samples):
            key = str(uuid.uuid5(uuid.NAMESPACE_URL, f'handover-demo-{index}'))
            state = mod.initial()
            state.pop('project', None)
            state['handover'] = dict(id=key, name=name, scope=scope,
                owner_id=owner, successor_id=successor,
                owner=users[owner]['name'], successor=users[successor]['name'],
                start_date='2026-10-19', end_date='2026-10-30', created_at=mod.now())
            db.execute('INSERT OR IGNORE INTO handovers VALUES (?, ?)', (key, json.dumps(state, ensure_ascii=False)))
        db.commit()


if __name__ == '__main__':
    seed()
