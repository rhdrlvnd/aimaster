"""Learning urgency labels shared by generation, review and scheduling."""
from typing import Literal

Priority = Literal['긴급', '보통', '여유']

LEGACY_LABELS = {'높음': '긴급', '낮음': '여유'}
FINGERPRINT_LABELS = {'긴급': '높음', '여유': '낮음'}
PRIORITY_ORDER = {'긴급': 0, '보통': 1, '여유': 2}

PRIORITY_RULES = '''
[중요도 판단 기준]
priority는 일반적인 업무 영향도 점수가 아니라 후임자가 인수인계 기간 중 언제 파악해야 하는지에 대한 제안이다. 긴급/보통/여유 중 하나만 사용한다.
- 긴급: 인수인계 기간 초반에 반드시 파악해야 할 항목. 장애 대응·서비스 가용성과 직결되는 업무처럼, 알지 못하면 초반부터 핵심 업무 수행이나 대응에 문제가 생기는 내용을 문서 근거로 판단한다.
- 보통: 기간 절반 이내 파악하면 되는 항목. 정기 운영·배포 등 주기적으로 수행하는 업무가 해당한다.
- 여유: 기간 내 여유롭게 파악해도 되는 항목. 참고·히스토리·문서화 등 즉시 업무 수행과 직접 연결되지 않는 내용이 해당한다.
개발뿐 아니라 인사·재무·법무 등 문서의 실제 업무 맥락에 동일한 기준을 적용한다. 모든 항목을 긴급으로 분류하거나 문서에 없는 마감·위험을 만들어 긴급으로 올리지 마라.
분류는 원문의 업무 목적과 조건을 근거로 제안하고, 선행 업무 관계와는 구분한다. 참고 문서라는 파일 이름만으로 여유로 정하지 말고 그 안의 실제 업무를 판단한다.
'''


def normalize_priority(value):
    """Rename historical labels without reclassifying or guessing invalid values."""
    return LEGACY_LABELS.get(value, value) if isinstance(value, str) else value


def normalize_state_priorities(state):
    """The caller supplies a freshly decoded state; this does not persist changes."""
    for item in state.get('items', []):
        if 'priority' in item:
            item['priority'] = normalize_priority(item['priority'])
    return state


def fingerprint_items(items):
    """Keep hashes stable for a label rename, without ignoring content changes."""
    return [
        {**item, 'priority': FINGERPRINT_LABELS.get(item['priority'], item['priority'])}
        if 'priority' in item else dict(item)
        for item in items
    ]
