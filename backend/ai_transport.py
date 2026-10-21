"""Bounded retries for upstream availability errors; never log request content."""
import asyncio
import logging
import time

log = logging.getLogger('uvicorn.error.handover.transport')

async def post(client, url, *, label, report=None, stage='analyze', **kwargs):
    for attempt in range(2):
        started = time.monotonic()
        response = await client.post(url, **kwargs)
        log.info('operation=%s attempt=%s status=%s elapsed=%.2f',
                 label, attempt + 1, response.status_code, time.monotonic() - started)
        if response.status_code not in (502, 503, 504) or attempt == 1:
            return response
        if report:
            report(stage, f'{label}: AI 서버가 HTTP {response.status_code}를 반환했습니다. 3초 후 자동 재시도합니다 (1/1). 기존 자료는 유지됩니다.')
        await asyncio.sleep(3)
        if report:
            report(stage, f'{label}: AI 서버 응답을 다시 기다리고 있습니다 (자동 재시도 1/1).')
