"""Version B isolated public preview.

Unlike the V1.8 legacy app, this ASGI entrypoint mounts ONLY the Version B
enterprise APIs. Each anonymous visitor receives a short-lived signed identity
with a unique tenant; no operator password is published or required.
"""
from __future__ import annotations
import base64
import hashlib
import hmac
import json
import os
import threading
import time
import uuid
from collections import defaultdict, deque
from urllib.parse import urlsplit
from pathlib import Path
from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from enterprise_workbench.rc2 import Identity, identity, router as rc2_router
from enterprise_workbench.rc4 import router as rc4_router
from enterprise_workbench.integration import router as cap_router

BASE=Path(__file__).resolve().parents[1]
SESSION_TTL=60*60*2
_lock=threading.Lock()
_issued=deque()
_traffic=defaultdict(deque)
_writes=defaultdict(deque)


def _secret():
    raw=os.environ.get('PREVIEW_SESSION_SECRET', '')
    if len(raw)<48:
        raise RuntimeError('PREVIEW_SESSION_SECRET must be at least 48 characters')
    return raw.encode('utf-8')


def _sign(raw):
    return hmac.new(_secret(),raw,hashlib.sha256).digest()


def _b64(data):
    return base64.urlsafe_b64encode(data).decode('ascii').rstrip('=')


def _unb64(text):
    return base64.urlsafe_b64decode(text+'='*(-len(text)%4))


def issue_session():
    now=int(time.time())
    payload={'v':1,'tenant':'guest-'+uuid.uuid4().hex, 'actor':'visitor',
             'role':'admin','iat':now,'exp':now+SESSION_TTL}
    raw=json.dumps(payload,separators=(',',':'),sort_keys=True).encode()
    return _b64(raw)+'.'+_b64(_sign(raw)),payload


def preview_identity(request:Request):
    authorization=request.headers.get('authorization','')
    if not authorization.startswith('Bearer '):
        raise HTTPException(401,detail='PREVIEW_SESSION_REQUIRED')
    try:
        token=authorization.removeprefix('Bearer ')
        raw64,mac64=token.split('.')
        if len(token)>1024:raise ValueError()
        raw=_unb64(raw64)
        if not hmac.compare_digest(_sign(raw),_unb64(mac64)):raise ValueError()
        payload=json.loads(raw)
        now=int(time.time())
        if payload.get('v')!=1 or payload.get('iat',0)>now or payload.get('exp',0)<=now:
            raise ValueError()
        if payload.get('exp',0)-payload.get('iat',0)>SESSION_TTL:raise ValueError()
        tenant=payload.get('tenant','')
        if not isinstance(tenant,str) or not tenant.startswith('guest-') or len(tenant)!=38:
            raise ValueError()
        return Identity(actor='visitor',tenant=tenant,role='admin')
    except (ValueError,TypeError,KeyError,UnicodeError,IndexError,json.JSONDecodeError):
        raise HTTPException(401,detail='INVALID_OR_EXPIRED_PREVIEW_SESSION') from None


def create_app():
    # Fail closed on missing signing secret; deployment must explicitly configure it.
    _secret()
    app=FastAPI(title='Industrial AI PaaS Lab — Version B Preview',version='1.9-b-preview')
    app.dependency_overrides[identity]=preview_identity
    app.include_router(rc2_router)
    app.include_router(rc4_router)
    app.include_router(cap_router)

    @app.middleware('http')
    async def preview_perimeter(request:Request,call_next):
        path=request.url.path
        # Server generated tokens, no cross-origin token issuance and no cookie auth.
        origin=request.headers.get('origin')
        if origin:
            o=urlsplit(origin)
            if o.scheme not in ('https','http') or not o.netloc or o.netloc.lower()!=request.headers.get('host','').lower():
                return JSONResponse({'detail':'CROSS_ORIGIN_NOT_ALLOWED'},status_code=403)
        if request.method not in ('GET','HEAD','OPTIONS','POST'):
            return JSONResponse({'detail':'METHOD_NOT_ALLOWED'},status_code=405)
        if request.method=='POST' and path not in (
            '/api/v1/version-b/preview/session',
            '/api/v1/version-b/enterprise/mrp/runs',
            '/api/v1/version-b/enterprise/decisions',
            '/api/v1/version-b/enterprise/worker/dispatch',
            '/api/v1/version-b/enterprise/reconciliation',
            '/api/v1/version-b/enterprise/reconciliation/verified',
            '/api/v1/version-b/enterprise/reconciliation/dynamic',
            '/api/v1/version-b/enterprise/what-if',
            '/api/v1/version-b/enterprise/mcp/tools/call',
            '/api/v1/version-b/enterprise/mcp/rpc',
        ):
            return JSONResponse({'detail':'PREVIEW_ROUTE_NOT_ALLOWED'},status_code=403)
        # A simple single-worker budget. Not a distributed WAF or DDoS defense.
        now=time.monotonic()
        with _lock:
            while _traffic['global'] and _traffic['global'][0]<now-60:
                _traffic['global'].popleft()
            if len(_traffic['global'])>=240:
                return JSONResponse({'detail':'PREVIEW_BUSY_RETRY_LATER'},status_code=429)
            _traffic['global'].append(now)
        if request.method=='POST' and path!='/api/v1/version-b/preview/session':
            # Reject invalid credentials before tracking limits to avoid unbounded
            # in-memory keys supplied by anonymous visitors.
            try:
                preview_identity(request)
            except HTTPException as exc:
                return JSONResponse({'detail':exc.detail},status_code=exc.status_code)
            token=request.headers.get('authorization','')
            key=hashlib.sha256(token.encode('utf-8')).hexdigest()
            with _lock:
                expired=[k for k,v in _writes.items() if not v or v[-1]<now-SESSION_TTL]
                for k in expired:_writes.pop(k,None)
                w=_writes[key]
                while w and w[0]<now-SESSION_TTL:w.popleft()
                if len(w)>=25:
                    return JSONResponse({'detail':'PREVIEW_SESSION_WRITE_LIMIT'},status_code=429)
                w.append(now)
        response=await call_next(request)
        response.headers['Cache-Control']='no-store'
        response.headers['X-Content-Type-Options']='nosniff'
        response.headers['Referrer-Policy']='no-referrer'
        response.headers['X-Frame-Options']='DENY'
        return response

    @app.get('/health')
    def health():return {'status':'ok','edition':'version-b-preview','database_verified':False}

    @app.get('/ready')
    def ready():
        from app.db.repository import connect
        try:
            with connect() as conn:
                row=conn.execute('SELECT to_regclass(%s), current_setting(%s)',('version_b_rc2.workflow_states','server_version_num')).fetchone()
                if row[0] is None or not row[1].startswith('16'):raise ValueError('MIGRATIONS_OR_PG16_MISSING')
            return {'status':'ready','database':'postgresql','scope':'preview_only'}
        except Exception:
            return JSONResponse({'status':'unavailable','database':'unready'},status_code=503)

    @app.post('/api/v1/version-b/preview/session')
    def session():
        now=time.monotonic()
        with _lock:
            while _issued and _issued[0]<now-3600:_issued.popleft()
            if len(_issued)>=60:raise HTTPException(429,detail='PREVIEW_SESSION_LIMIT')
            _issued.append(now)
        token,payload=issue_session()
        return {'access_token':token,'expires_in':SESSION_TTL,'tenant':payload['tenant'],
                'role':'admin','scope':'ISOLATED_INTERNAL_DEMO','external_execution':False}

    @app.get('/',include_in_schema=False)
    def index():return RedirectResponse('/workbench/')

    app.mount('/workbench',StaticFiles(directory=str(BASE/'enterprise_workbench'/'site'),html=True),name='workbench')
    return app


app=create_app()
