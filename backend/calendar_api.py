"""Google OAuth and idempotent Calendar synchronization. Tokens stay server-side."""
import os, time, secrets, hashlib, base64
from urllib.parse import urlencode
from datetime import date, timedelta
import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse

TOKENS={}
PENDING={}

def config():
    return os.environ.get('GOOGLE_CLIENT_ID',''),os.environ.get('GOOGLE_CLIENT_SECRET',''),os.environ.get('GOOGLE_REDIRECT_URI','http://127.0.0.1:5185/api/calendar/callback')
def status(user):
    client,secret,_=config()
    return {'configured':bool(client and secret),'connected':user['id'] in TOKENS}

async def access_token(user):
    saved=TOKENS.get(user['id'])
    if not saved: raise HTTPException(409,'Google Calendar를 먼저 연결해 주세요.')
    if saved['expires_at']>time.time()+60: return saved['access_token']
    client,secret,_=config()
    async with httpx.AsyncClient(timeout=30) as http:
        r=await http.post('https://oauth2.googleapis.com/token',data={'client_id':client,'client_secret':secret,'refresh_token':saved.get('refresh_token',''),'grant_type':'refresh_token'})
    if r.status_code!=200:
        TOKENS.pop(user['id'],None);raise HTTPException(401,'Google 연결이 만료됐습니다. 다시 연결해 주세요.')
    value=r.json();saved.update(access_token=value['access_token'],expires_at=time.time()+value.get('expires_in',3600))
    return saved['access_token']

async def sync_events(user,state,ids):
    token=await access_token(user)
    schedule=state.get('schedule',{})
    if not schedule.get('confirmed'): raise HTTPException(409,'확정된 일정이 없습니다.')
    rows={r['item_id']:r for r in schedule['confirmed']}
    items={i['id']:i for i in state['items']}
    if set(ids)-set(rows): raise HTTPException(422,'확정 일정에 없는 업무입니다.')
    results=[]
    async with httpx.AsyncClient(timeout=30,headers={'Authorization':'Bearer '+token}) as http:
        for key in ids:
            row=rows[key]
            event_id='h'+hashlib.sha256((user['id']+state['handover']['id']+key).encode()).hexdigest()[:40]
            payload={'summary':items[key]['title'],'description':state['handover']['name']+'\n'+items[key]['description'],
                'start':{'date':row['start']},'end':{'date':(date.fromisoformat(row['end'])+timedelta(days=1)).isoformat()},
                'extendedProperties':{'private':{'handover_id':state['handover']['id'],'item_id':key}}}
            if row.get('start_time') and row.get('end_time'):
                if row['start']==row['end']:
                    payload['start']={'dateTime':row['start']+'T'+row['start_time'],'timeZone':'Asia/Seoul'}
                    payload['end']={'dateTime':row['end']+'T'+row['end_time'],'timeZone':'Asia/Seoul'}
                else:
                    # A date-range event must not imply overnight continuous work.
                    settings=schedule['settings']
                    payload['description']+=f"\n분할 진행: {row['start']} {row['start_time']} ~ {row['end']} {row['end_time']}. 하루 {settings['day_start']}시부터 {settings['daily_hours']}시간, 설정된 휴일 제외."
            url='https://www.googleapis.com/calendar/v3/calendars/primary/events'
            try:
                r=await http.post(url,json={**payload,'id':event_id})
                if r.status_code==409: r=await http.patch(url+'/'+event_id,json=payload)
                if r.status_code in (200,201): results.append({'item_id':key,'status':'success','event_id':event_id})
                else: results.append({'item_id':key,'status':'failed','detail':f'Google Calendar 응답 {r.status_code}'})
            except httpx.HTTPError:
                results.append({'item_id':key,'status':'failed','detail':'Google Calendar 연결 실패. 다시 시도해 주세요.'})
    return results

def install(m):
    router=APIRouter()
    @router.get('/api/calendar/status')
    def get_status(user=Depends(m.current_user)): return status(user)
    @router.post('/api/calendar/connect')
    def connect(request:Request,user=Depends(m.current_user)):
        client,secret,redirect=config()
        if not client or not secret: raise HTTPException(503,'Google OAuth 클라이언트 ID와 Secret 설정이 필요합니다.')
        verifier=secrets.token_urlsafe(48); nonce=secrets.token_urlsafe(32)
        PENDING[nonce]={'user':user['id'],'session':request.cookies.get('handover_session'),'created':time.time(),'verifier':verifier}
        challenge=base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip('=')
        return {'url':'https://accounts.google.com/o/oauth2/v2/auth?'+urlencode({'client_id':client,'redirect_uri':redirect,'response_type':'code',
            'scope':'https://www.googleapis.com/auth/calendar.events','access_type':'offline','prompt':'consent','state':nonce,'code_challenge':challenge,'code_challenge_method':'S256'})}
    @router.get('/api/calendar/callback')
    async def callback(request:Request,state:str='',code:str='',error:str=''):
        pending=PENDING.pop(state,None)
        if not pending or time.time()-pending['created']>600 or pending['session']!=request.cookies.get('handover_session') or m.SESSIONS.get(pending['session'])!=pending['user']:
            raise HTTPException(400,'Google 연결 요청이 만료되었거나 사용자가 일치하지 않습니다.')
        if error or not code: return RedirectResponse('/?calendar=cancelled')
        client,secret,redirect=config()
        try:
            async with httpx.AsyncClient(timeout=30) as http:
                r=await http.post('https://oauth2.googleapis.com/token',data={'client_id':client,'client_secret':secret,'redirect_uri':redirect,'code':code,'grant_type':'authorization_code','code_verifier':pending['verifier']})
        except httpx.HTTPError:
            raise HTTPException(502,'Google 인증 서버에 연결하지 못했습니다. 다시 연결해 주세요.')
        if r.status_code!=200: raise HTTPException(502,'Google 인증을 완료하지 못했습니다. 다시 연결해 주세요.')
        try:
            value=r.json()
            if not value.get('access_token'): raise ValueError()
        except (ValueError, AttributeError):
            raise HTTPException(502,'Google 인증 응답을 확인하지 못했습니다. 다시 연결해 주세요.')
        TOKENS[pending['user']]={'access_token':value['access_token'],'refresh_token':value.get('refresh_token',''),'expires_at':time.time()+value.get('expires_in',3600)}
        return RedirectResponse('/?calendar=connected')
    @router.delete('/api/calendar/connection')
    async def disconnect(user=Depends(m.current_user)):
        old=TOKENS.pop(user['id'],None)
        if old:
            try:
                async with httpx.AsyncClient(timeout=15) as http: await http.post('https://oauth2.googleapis.com/revoke',data={'token':old.get('refresh_token') or old['access_token']})
            except httpx.HTTPError: pass
        return {'ok':True}
    m.app.include_router(router)
