"""Strict local MCP stdio facade over the V1.5 audited gateway.

No HTTP listener, public network binding, credential acquisition, or release enablement.
Caller supplies a trusted, pre-authenticated invocation function. Default deny.
"""
from app.mcp_v15.stdio_server import ProtocolServer, PROTOCOL, error, serve
from app.mcp_v15.full_gateway import SPECS, validate, Rejected

class HardenedProtocolServer(ProtocolServer):
    def handle(self, message):
        if not isinstance(message, dict):
            return error(-32600, 'Invalid Request')
        method = message.get('method')
        if method == 'notifications/initialized':
            if message.get('jsonrpc') != '2.0' or 'id' in message or not self._handshake:
                return error(-32600, 'Invalid initialization notification') if 'id' in message else None
            self.initialized = True
            return None
        if method == 'initialize':
            if self._handshake:
                return error(-32600, 'Already initialized', message.get('id'))
            result = super().handle(message)
            if isinstance(result, dict) and 'result' in result:
                self._handshake = True
                result['result']['serverInfo']['version'] = '1.7.0'
            return result
        if method == 'tools/call' and self.initialized:
            params = message.get('params', {})
            if isinstance(params, dict):
                name = params.get('name')
                args = params.get('arguments', {})
                if name in SPECS:
                    try:
                        validate(name, args)
                    except (Rejected, ValueError, TypeError):
                        return error(-32602, 'Invalid tool arguments', message.get('id'))
        return super().handle(message)

    def __init__(self, invoke, enabled=False):
        super().__init__(invoke, enabled=enabled)
        self._handshake = False

__all__ = ['HardenedProtocolServer', 'serve', 'PROTOCOL']
