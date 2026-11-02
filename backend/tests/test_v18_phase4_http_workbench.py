"""Live localhost HTTP and Workbench route smoke; not a browser UX certification."""
import json
import threading
import urllib.request
import urllib.error
from pathlib import Path
from app.mcp_v18.http_transport import MCPHTTPServer


def test_real_loopback_http_auth_and_session():
    calls=[]
    srv=MCPHTTPServer(('127.0.0.1',0),lambda *args: calls.append(args), 'z'*40)
    thread=threading.Thread(target=srv.serve_forever,daemon=True)
    thread.start()
    try:
        def post(payload,headers=None):
            req=urllib.request.Request('http://127.0.0.1:%d/mcp'%srv.server_port,
                data=json.dumps(payload).encode(),headers={'Content-Type':'application/json','Accept':'application/json',**(headers or {})})
            try:
                with urllib.request.urlopen(req,timeout=3) as r:
                    return r.status,dict(r.headers),json.loads(r.read())
            except urllib.error.HTTPError as e:
                return e.code,dict(e.headers),json.loads(e.read())
        init={'jsonrpc':'2.0','id':1,'method':'initialize','params':{'protocolVersion':'2024-11-05'}}
        assert post(init)[0]==401
        assert post(init,{'Authorization':'Bearer '+'z'*40,'Origin':'https://evil.invalid'})[0]==403
        code,headers,payload=post(init,{'Authorization':'Bearer '+'z'*40})
        assert code==200 and 'result' in payload
        sid=headers['Mcp-Session-Id']
        assert post({'jsonrpc':'2.0','id':2,'method':'tools/call','params':{'name':'mrp.get_run','arguments':{'run_id':'R1'}}},
                    {'Authorization':'Bearer '+'z'*40,'Mcp-Session-Id':sid})[2]['error']['code']==-32000
        assert not calls
    finally:
        srv.shutdown();srv.server_close();thread.join(timeout=3)


def test_workbench_static_assets_present_and_database_not_faked():
    from app.main import app
    from fastapi.testclient import TestClient
    client=TestClient(app)
    # No DB credentials are provided; route contract must exist, never fabricate a snapshot.
    # FastAPI 0.1xx may keep included routers as deferred _IncludedRouter
    # objects in app.routes. OpenAPI expands the effective route tree and is
    # the stable public contract for registered HTTP endpoints.
    paths = set(client.get('/openapi.json').json().get('paths', {}))
    assert '/api/v1/workbench/snapshot' in paths
    assert '/api/v1/workbench/workflows/{workflow_id}/history' in paths
    assets=Path(__file__).resolve().parents[1]/'app'/'web'
    assert (assets/'v17.html').is_file()
    assert (assets/'v17.js').is_file()
    assert 'snapshot' in (assets/'v17.js').read_text(encoding='utf-8')
    assert client.get('/health').status_code==200
