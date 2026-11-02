"""Loopback-only, opt-in MCP Streamable HTTP-compatible JSON-RPC subset.

Development demonstration only. Not an internet-facing MCP endpoint: no OAuth,
SSE/resumability, multi-worker session store or remote authentication.
Never mounts into the production FastAPI app.
"""
import json
import secrets
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit
from .transport import HardenedProtocolServer

MAX_BODY = 1024 * 1024

class LocalMCPHTTP(ThreadingHTTPServer):
    daemon_threads = True
    def __init__(self, address, invoke, token, enabled=False):
        host, _ = address
        if host not in ('127.0.0.1', '::1'):
            raise ValueError('LOOPBACK_ONLY')
        if not isinstance(token, str) or len(token) < 32:
            raise ValueError('LOCAL_TOKEN_REQUIRED')
        self.access_token = token
        self.protocol = HardenedProtocolServer(invoke, enabled=enabled)
        self.lock = __import__('threading').Lock()
        super().__init__(address, LocalHandler)

class LocalHandler(BaseHTTPRequestHandler):
    server_version = 'IndustrialMCP/1.7'
    def log_message(self, fmt, *args):
        pass  # Do not leak headers or request bodies
    def reply(self, code, obj=None):
        body = b'' if obj is None else json.dumps(obj, ensure_ascii=False).encode('utf8')
        self.send_response(code)
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        if body: self.wfile.write(body)
    def do_GET(self):
        if urlsplit(self.path).path == '/health':
            return self.reply(200, {'service':'mcp-v17-local','enabled':self.server.protocol.enabled})
        return self.reply(404, {'error':'not_found'})
    def do_POST(self):
        if urlsplit(self.path).path != '/mcp': return self.reply(404, {'error':'not_found'})
        if not secrets.compare_digest(self.headers.get('Authorization',''), 'Bearer '+self.server.access_token):
            return self.reply(401, {'error':'unauthorized'})
        if self.headers.get('Content-Type','').split(';')[0].strip().lower() != 'application/json':
            return self.reply(415, {'error':'unsupported_media_type'})
        try:
            n=int(self.headers.get('Content-Length','-1'))
        except ValueError: return self.reply(400, {'error':'invalid_length'})
        if n<0 or n>MAX_BODY: return self.reply(413, {'error':'invalid_size'})
        try:
            request=json.loads(self.rfile.read(n))
        except (UnicodeError,ValueError):
            return self.reply(400, {'jsonrpc':'2.0','id':None,'error':{'code':-32700,'message':'Parse error'}})
        with self.server.lock:
            response=self.server.protocol.handle(request)
        return self.reply(202 if response is None else 200,response)
