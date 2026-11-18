"""Extension of the existing authenticated API; no worker runs in a request."""
import re
from .bridge import Bridge
from .memory_tools import MemoryTools
from .validation import loads


def dispatch(memory, principal, request, url, query, *, searcher=None):
    if not url.path.startswith('/v1/missions') and url.path != '/v1/tools/call': return None
    bridge = Bridge(memory, principal)
    if url.path == '/v1/missions' and request.command == 'GET':
        if set(query) - {'limit'}: raise ValueError('Mission list filters')
        return 200, {'items': bridge.list(int(query.get('limit', 50)))}, 'application/json'
    body = {}
    if request.command == 'POST':
        size = int(request.headers.get('Content-Length', 0))
        if not 0 < size <= 16000 or request.headers.get('Transfer-Encoding'): raise ValueError('Body limit')
        body = loads(request.rfile.read(size))
    if url.path == '/v1/tools/call' and request.command == 'POST':
        if set(body) != {'name', 'arguments'}: raise ValueError('Tool envelope')
        # No caller-provided mission binding; results use a mission-scoped endpoint.
        if body['name'] == 'mission.result': raise PermissionError('Mission binding required')
        return 200, {'result': MemoryTools(memory, principal, searcher=searcher).call(body['name'], body['arguments'])}, 'application/json'
    if url.path == '/v1/missions' and request.command == 'POST':
        if set(body) - {'definition', 'scope'}: raise ValueError('Admission fields')
        mid = bridge.submit(request.headers.get('Idempotency-Key', ''), body['definition'], body.get('scope', 'private'))
        return 202, {'mission_id': mid, 'state': bridge.get(mid)['state']}, 'application/json'
    match = re.fullmatch(r'/v1/missions/([a-zA-Z0-9-]+)(?:/(events|cancel|approvals|results|result))?', url.path)
    if not match: return 404, {'error': 'Unknown mission route'}, 'application/json'
    mid, action = match.groups()
    if request.command == 'GET' and action in {None, 'results'}:
        return 200, bridge.get(mid) if action is None else {'events': bridge.events(mid), 'validation': 'unreviewed'}, 'application/json'
    if request.command == 'GET' and action == 'events':
        after = int(request.headers.get('Last-Event-ID', query.get('after', 0)))
        rows = bridge.events(mid, after)
        # Finite SSE pages close; clients reconnect with Last-Event-ID. No polling
        # loop or agent work occupies the vocal HTTP handler.
        text = ''.join('id: ' + str(r['seq']) + '\nevent: ' + r['kind'] + '\ndata: ' + r['data'] + '\n\n' for r in rows)
        return 200, text or ': idle\n\n', 'text/event-stream'
    if request.command == 'POST' and action == 'cancel': return 202, bridge.cancel(mid), 'application/json'
    if request.command == 'POST' and action == 'approvals':
        return 202, bridge.decide(mid, body['approval_id'], body['fingerprint'], body['choice']), 'application/json'
    if request.command == 'POST' and action == 'result':
        return 201, {'memory_ids': MemoryTools(memory, principal, mid).call('mission.result', body)}, 'application/json'
    return 404, {'error': 'Unknown mission operation'}, 'application/json'
