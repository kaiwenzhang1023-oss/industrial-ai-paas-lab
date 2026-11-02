"""Real loopback HTTP smoke + fail-closed recovery + Workbench static demo contract."""
import json
import threading
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from app.mcp_v17.http_transport import LocalMCPHTTP
from app.mcp_v17.recovery import classify

TOKEN = 'v17-final-smoke-token-' + 'x' * 40


def _request(server, path, method='GET', payload=None, authorized=True):
    headers = {'Content-Type': 'application/json'}
    if authorized:
        headers['Authorization'] = 'Bearer ' + TOKEN
    data = json.dumps(payload).encode() if payload is not None else None
    request = urllib.request.Request(f'http://127.0.0.1:{server.server_port}{path}', data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=3) as response:
            return response.status, json.loads(response.read() or b'null')
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read() or b'null')


def test_real_http_end_to_end_default_deny():
    invoked = []
    server = LocalMCPHTTP(('127.0.0.1', 0), lambda *args: invoked.append(args), TOKEN, enabled=False)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        status, health = _request(server, '/health')
        assert status == 200 and health['enabled'] is False
        status, _ = _request(server, '/mcp', 'POST', {'jsonrpc':'2.0','id':1,'method':'initialize'}, authorized=False)
        assert status == 401
        status, init = _request(server, '/mcp', 'POST', {'jsonrpc':'2.0','id':1,'method':'initialize','params':{}})
        assert status == 200 and init['result']['serverInfo']['version'] == '1.7.0'
        status, _ = _request(server, '/mcp', 'POST', {'jsonrpc':'2.0','method':'notifications/initialized'})
        assert status == 202
        status, listed = _request(server, '/mcp', 'POST', {'jsonrpc':'2.0','id':2,'method':'tools/list'})
        assert status == 200 and len(listed['result']['tools']) == 5
        status, denied = _request(server, '/mcp', 'POST', {'jsonrpc':'2.0','id':3,'method':'tools/call','params':{'name':'mrp.get_run','arguments':{'run_id':'test'}}})
        assert status == 200 and denied['error']['code'] == -32003 and not invoked
        status, _ = _request(server, '/not-mcp', 'POST', {})
        assert status == 404
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=3)


@pytest.mark.parametrize(('state','age','expected'), [
    ('DONE', 999, 'RETURN_CACHED'),
    ('IN_PROGRESS', 10, 'WAIT'),
    ('IN_PROGRESS', 301, 'MANUAL_REVIEW'),
    ('FAILED', 301, 'MANUAL_REVIEW'),
    ('IN_PROGRESS', -1, 'MANUAL_REVIEW'),
])
def test_recovery_fail_closed(state, age, expected):
    assert classify(state, age).action == expected


def test_workbench_static_demo_contract():
    root = Path(__file__).resolve().parents[1] / 'app' / 'web'
    html = (root / 'v17.html').read_text(encoding='utf-8')
    js = (root / 'v17.js').read_text(encoding='utf-8')
    assert 'id="state"' in html and 'id="counts"' in html
    assert '/workbench/v17.js' in html
    assert '/api/v1/workbench/snapshot' in js
    assert 'if(!r.ok)' in js and '只读快照不可用' in js
    assert '模拟成功' not in js.split('catch(e)')[0]
