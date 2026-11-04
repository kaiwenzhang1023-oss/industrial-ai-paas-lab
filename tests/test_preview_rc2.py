"""Offline public-preview perimeter regression. No cloud/PG assertions."""
import os,sys,base64,json,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
os.environ.setdefault('PREVIEW_SESSION_SECRET','local-test-only-key-not-for-production-0123456789abcdef')
sys.path[:0]=[str(ROOT),str(ROOT/'backend')]
from fastapi.testclient import TestClient
from preview_cloud.app import app,_b64,_sign
c=TestClient(app)
API='/api/v1/version-b/enterprise'
SESSION='/api/v1/version-b/preview/session'

def issue():
    r=c.post(SESSION)
    assert r.status_code==200
    return r.json()

def test_health_only_process():
    r=c.get('/health');assert r.status_code==200
    assert r.json()['database_verified'] is False

def test_readiness_fails_closed_without_dsn(monkeypatch):
    monkeypatch.delenv('DATABASE_URL',raising=False)
    r=c.get('/ready');assert r.status_code==503
    assert r.json()['database']=='unready'

def test_static_workbench():
    assert c.get('/workbench/').status_code==200
    r=c.get('/workbench/enterprise-status.js')
    assert r.status_code==200
    assert b'vbEnterpriseTab' in r.content

def test_public_session_identity():
    x=issue();assert x['tenant'].startswith('guest-')
    r=c.get(API+'/me',headers={'Authorization':'Bearer '+x['access_token']})
    assert r.status_code==200
    assert r.json()['tenant']==x['tenant']

def test_unique_tenants():
    a=issue();b=issue();assert a['tenant']!=b['tenant']
    assert a['access_token']!=b['access_token']

def test_missing_token_rejected():
    assert c.get(API+'/me').status_code==401
    assert c.post(API+'/mrp/runs').status_code==401

def test_tampered_token_rejected():
    token=issue()['access_token']
    assert c.get(API+'/me',headers={'Authorization':'Bearer '+token[:-1]+'Z'}).status_code==401

def test_expired_token_rejected():
    token=issue()['access_token'];raw=base64.urlsafe_b64decode(token.split('.')[0]+'==')
    j=json.loads(raw);j['iat']=int(time.time())-10000;j['exp']=int(time.time())-9000
    dat=json.dumps(j,separators=(',',':'),sort_keys=True).encode()
    crafted=_b64(dat)+'.'+_b64(_sign(dat))
    assert c.get(API+'/me',headers={'Authorization':'Bearer '+crafted}).status_code==401

def test_cross_origin_rejected():
    r=c.post(SESSION,headers={'Origin':'https://evil.example'})
    assert r.status_code==403

def test_unknown_post_rejected():
    token=issue()['access_token']
    r=c.post('/api/v1/unrelated/unsafe',headers={'Authorization':'Bearer '+token})
    assert r.status_code==403

def test_legacy_mutation_absent():
    assert c.post('/api/v1/mrp/run').status_code==403

def test_method_guard():
    assert c.delete('/api/v1/version-b/enterprise/mrp/runs').status_code==405

def test_capabilities_not_production():
    r=c.get('/api/v1/version-b/capabilities')
    assert r.status_code==200 and r.json()['production_ready'] is False

def test_no_secret_in_status():
    assert 'DATABASE_URL' not in c.get('/health').text
    assert 'PREVIEW_SESSION_SECRET' not in c.get('/ready').text
