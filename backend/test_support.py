"""Provide an explicitly selected handover for existing workflow regression tests."""
from fastapi.testclient import TestClient

class ScopedTestClient(TestClient):
    def __init__(self, module):
        self.prefix = None
        self.module = module
        super().__init__(module.app)
        self.post('/api/demo/session', json={'user_id':'demo-dev'}).raise_for_status()
        response = self.post('/api/handovers', json={
            'name':'회귀 검증', 'scope':'업무 문서 처리', 'owner':'김개발', 'successor':'이후임',
            'start_date':'2026-10-19', 'end_date':'2026-10-30'})
        response.raise_for_status()
        handover_id=response.json()['id']
        self.prefix='/api/handovers/'+handover_id
        self.token=module.HANDOVER_ID.set(handover_id)

    def request(self, method, url, *args, **kwargs):
        if self.prefix and str(url).startswith('/api/') and not str(url).startswith('/api/handovers'):
            url=self.prefix+str(url)[4:]
        return super().request(method,url,*args,**kwargs)

    def close(self):
        self.module.HANDOVER_ID.reset(self.token)
        super().close()
