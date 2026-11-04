"""Google OAuth for Tasks and legacy Calendar migration. Tokens stay server-side."""
import os, time, secrets, hashlib, base64
from urllib.parse import urlencode
import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse, JSONResponse
from backend import google_store

TOKENS={}
PENDING={}
TASKS_SCOPE='https://www.googleapis.com/auth/tasks'
SCOPES='openid '+TASKS_SCOPE+' https://www.googleapis.com/auth/calendar.events'

def saved_token(user_id):
    # Memory-only tokens from earlier releases require Tasks consent again.
    return google_store.account(user_id) or TOKENS.get(user_id)

def config():
    return os.environ.get('GOOGLE_CLIENT_ID',''),os.environ.get('GOOGLE_CLIENT_SECRET',''),os.environ.get('GOOGLE_REDIRECT_URI','http://127.0.0.1:5185/api/calendar/callback')
def status(user):
    client,secret,_=config()
    try: saved=saved_token(user['id'])
    except HTTPException: saved={}
    ready=bool(saved and saved.get('account_id') and TASKS_SCOPE in saved.get('scope','').split())
    return {'configured':bool(client and secret),'connected':ready,'needs_reconnect':saved is not None and not ready,'provider':'tasks'}

async def access_token(user):
    saved=saved_token(user['id'])
    if not saved: raise HTTPException(409,'Google Tasks를 먼저 연결해 주세요.')
    if saved['expires_at']>time.time()+60: return saved['access_token']
    client,secret,_=config()
    async with httpx.AsyncClient(timeout=30) as http:
        r=await http.post('https://oauth2.googleapis.com/token',data={'client_id':client,'client_secret':secret,'refresh_token':saved.get('refresh_token',''),'grant_type':'refresh_token'})
    if r.status_code!=200:
        if r.status_code in (400,401):
            TOKENS.pop(user['id'],None);google_store.delete_account(user['id'])
        raise HTTPException(401 if r.status_code in (400,401) else 502,'Google 연결을 갱신하지 못했습니다. 연결 상태를 확인해 주세요.')
    value=r.json();saved.update(access_token=value['access_token'],expires_at=time.time()+value.get('expires_in',3600))
    if value.get('refresh_token'): saved['refresh_token']=value['refresh_token']
    if saved.get('account_id'): google_store.save_account(user['id'],saved)
    return saved['access_token']


def install(m):
    google_store.configure(lambda:m.DB)
    router=APIRouter()
    @router.get('/api/calendar/status')
    def get_status(user=Depends(m.current_user)): return status(user)
    @router.post('/api/calendar/connect')
    def connect(request:Request,user=Depends(m.current_user)):
        client,secret,redirect=config()
        if not client or not secret: raise HTTPException(503,'Google OAuth 클라이언트 ID와 Secret 설정이 필요합니다.')
        verifier=secrets.token_urlsafe(48); nonce=secrets.token_urlsafe(32)
        binding=secrets.token_urlsafe(32)
        PENDING[nonce]={'user':user['id'],'session':request.cookies.get('handover_session'),'created':time.time(),'verifier':verifier,'binding':binding}
        challenge=base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip('=')
        response=JSONResponse({'url':'https://accounts.google.com/o/oauth2/v2/auth?'+urlencode({'client_id':client,'redirect_uri':redirect,'response_type':'code',
            'scope':SCOPES,'access_type':'offline','prompt':'consent','state':nonce,'code_challenge':challenge,'code_challenge_method':'S256'})})
        # Only this short-lived OAuth binding crosses the Google redirect.
        # The application's authentication cookie remains SameSite=Strict.
        response.set_cookie('handover_oauth',binding,max_age=600,httponly=True,samesite='lax',secure=redirect.startswith('https://'),path='/api/calendar/callback')
        return response
    @router.get('/api/calendar/callback')
    async def callback(request:Request,state:str='',code:str='',error:str=''):
        pending=PENDING.pop(state,None)
        if not pending or time.time()-pending['created']>600 or not secrets.compare_digest(pending.get('binding',''),request.cookies.get('handover_oauth','')) or not pending.get('binding') or m.SESSIONS.get(pending['session'])!=pending['user'] or (request.cookies.get('handover_session') and request.cookies['handover_session']!=pending['session']):
            raise HTTPException(400,'Google 연결 요청이 만료되었거나 사용자가 일치하지 않습니다.')
        def completed(url):
            response=RedirectResponse(url)
            response.delete_cookie('handover_oauth',path='/api/calendar/callback')
            return response
        if error or not code: return completed('/?calendar=cancelled')
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
        if TASKS_SCOPE not in value.get('scope','').split():
            raise HTTPException(403,'Google Tasks 접근에 동의하지 않았습니다. 다시 연결해 주세요.')
        try:
            async with httpx.AsyncClient(timeout=30) as http:
                identity=await http.get('https://openidconnect.googleapis.com/v1/userinfo',headers={'Authorization':'Bearer '+value['access_token']})
            if identity.status_code!=200 or not identity.json().get('sub'): raise ValueError()
            account_id=identity.json()['sub']
        except (httpx.HTTPError,ValueError):
            raise HTTPException(502,'연결한 Google 계정을 확인하지 못했습니다. 다시 연결해 주세요.')
        try: old=saved_token(pending['user'])
        except HTTPException: old=None
        refresh=value.get('refresh_token') or (old.get('refresh_token') if old and old.get('account_id')==account_id else None)
        if not refresh:
            raise HTTPException(409,'일일 동기화에 필요한 Google 연결 갱신 권한을 받지 못했습니다. 다시 연결해 주세요.')
        google_store.save_account(pending['user'],{'access_token':value['access_token'],'refresh_token':refresh,'expires_at':time.time()+value.get('expires_in',3600),'scope':value['scope'],'account_id':account_id})
        TOKENS.pop(pending['user'],None)
        return completed('/?calendar=connected')
    @router.delete('/api/calendar/connection')
    async def disconnect(user=Depends(m.current_user)):
        try: old=saved_token(user['id'])
        except HTTPException: old=None
        TOKENS.pop(user['id'],None)
        google_store.delete_account(user['id'])
        if old:
            try:
                async with httpx.AsyncClient(timeout=15) as http: await http.post('https://oauth2.googleapis.com/revoke',data={'token':old.get('refresh_token') or old['access_token']})
            except httpx.HTTPError: pass
        return {'ok':True}
    m.app.include_router(router)
