import asyncio
import base64
import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import backend.app
import httpx
from urllib.parse import quote

async def main():
    url = os.environ['LLM_BASE_URL'].rstrip('/') + '/openai/deployments/' + quote(os.environ.get('LLM_CHAT_MODEL','gpt-4.1-mini'), safe='') + '/chat/completions'
    image = base64.b64encode(Path('.artifact-build/handover-set/slide-1.png').read_bytes()).decode()
    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(url, params={'api-version':os.environ['LLM_API_VERSION']}, headers={'api-key':os.environ['LLM_API_KEY']}, json={
            'messages':[{'role':'user','content':[{'type':'text','text':'Read only the title in this image.'},{'type':'image_url','image_url':{'url':'data:image/png;base64,'+image}}]}], 'max_tokens':100})
        print('HTTP',r.status_code)
        if r.status_code == 200:
            print(r.json()['choices'][0]['message']['content'])
asyncio.run(main())
