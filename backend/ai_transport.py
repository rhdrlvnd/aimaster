"""Bounded retries for upstream availability errors; never log request content."""
import asyncio
import logging
import time
from email.utils import parsedate_to_datetime


def retry_delay(response):
    if response.status_code != 429:
        return 3
    raw=response.headers.get('Retry-After')
    if isinstance(raw,str):
        try:
            seconds=float(raw)
        except ValueError:
            try: seconds=parsedate_to_datetime(raw).timestamp()-time.time()
            except (ValueError,TypeError,OverflowError): seconds=60
        return max(1,min(120,seconds))
    return 60

log = logging.getLogger('uvicorn.error.handover.transport')

async def post(client, url, *, label, report=None, stage='analyze', **kwargs):
    for attempt in range(2):
        started = time.monotonic()
        response = await client.post(url, **kwargs)
        log.info('operation=%s attempt=%s status=%s elapsed=%.2f',
                 label, attempt + 1, response.status_code, time.monotonic() - started)
        if response.status_code not in (429, 502, 503, 504) or attempt == 1:
            return response
        delay=retry_delay(response)
        if report:
            report(stage, f'{label}: AI 서버가 HTTP {response.status_code}를 반환했습니다. {delay:g}초 후 자동 재시도합니다 (1/1). 기존 자료는 유지됩니다.')
        await asyncio.sleep(delay)
        if report:
            report(stage, f'{label}: AI 서버 응답을 다시 기다리고 있습니다 (자동 재시도 1/1).')
