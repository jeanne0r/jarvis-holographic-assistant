"""Loopback-only HTTP prototype. No production gateway integration.

Client file is a private JSON object keyed by SHA256(bearer token), mapping to
{name, scopes, roles}. It contains no cleartext tokens. Roles cannot be supplied
through requests. HTTP clients can only read and propose inferred knowledge.
"""
import argparse
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import time
from urllib.parse import parse_qs, urlsplit
from .store import Memory, Principal


def server(database, clients, port=0, *, extension=None):
    # Privileged ingest/review interfaces intentionally absent from HTTP.
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass  # Avoid personal query text, tokens and content in access logs.

        def dispatch(self):
            bearer = self.headers.get('Authorization', '')
            identity = clients.get(hashlib.sha256(bearer[7:].encode()).hexdigest()) if bearer.startswith('Bearer ') else None
            if not identity:
                return self.reply(401, {'error': 'Authentication required'})
            principal = Principal(identity['name'], frozenset(identity['scopes']), frozenset(identity.get('roles', ['reader', 'proposer'])), identity.get('actor_id', ''))
            parsed = urlsplit(self.path)
            args = {k: v[-1] for k, v in parse_qs(parsed.query).items()}
            db = None
            try:
                db = Memory(database)
                if extension:
                    result = extension(db, principal, self, parsed, args)
                    if result is not None:
                        return self.reply(*result)
                if self.command == 'GET' and parsed.path == '/v1/health':
                    return self.reply(200, {'ready': True, 'schema': 1, 'experimental': True})
                if self.command == 'GET' and parsed.path == '/v1/search':
                    if set(args) - {'q', 'type', 'subject', 'limit'}:
                        raise ValueError('Unknown filter')
                    return self.reply(200, {'items': db.search(principal, args.get('q', ''), memory_type=args.get('type'), subject=args.get('subject'), limit=int(args.get('limit', 10)))})
                if self.command == 'GET' and parsed.path == '/v1/history':
                    return self.reply(200, {'items': db.history(principal, args['memory_id'])})
                if self.command == 'POST' and parsed.path == '/v1/proposals':
                    length = int(self.headers.get('Content-Length', '0'))
                    if not 0 < length <= 64000 or self.headers.get('Transfer-Encoding'):
                        raise ValueError('Bounded Content-Length required')
                    data = json.loads(self.rfile.read(length))
                    if set(data) - {'key', 'reference', 'candidates', 'scope'}:
                        raise ValueError('Unknown proposal field')
                    for candidate in data['candidates']:
                        if set(candidate) - {'type', 'subject', 'predicate', 'content', 'confidence'}:
                            raise PermissionError('Proposal cannot select status, identity or correction')
                        candidate['status'] = 'inferred'
                    # Source time and channel come from the server. No trusted
                    # user/measurement ingestion is reachable from this endpoint.
                    # A stable request key uses a stable source timestamp on retry.
                    prior = db.db.execute('SELECT source FROM mm_events WHERE owner=? AND scope=? AND event_key=?',
                                          (principal.name, data.get('scope', 'private'), data['key'])).fetchone()
                    observed = json.loads(prior[0])['observed_at'] if prior else time.time()
                    ids = db.ingest(principal, data['key'], {'kind': 'external', 'ref': data['reference'], 'observed_at': observed},
                                    data['candidates'], scope=data.get('scope', 'private'))
                    return self.reply(201, {'memory_ids': ids, 'validation': 'inferred'})
                return self.reply(404, {'error': 'Unknown endpoint'})
            except PermissionError:
                return self.reply(403, {'error': 'Capability or scope denied'})
            except (KeyError, ValueError, TypeError):
                return self.reply(400, {'error': 'Invalid request'})
            except Exception:
                return self.reply(503, {'error': 'Memory unavailable'})
            finally:
                if db:
                    db.close()

        def reply(self, status, value, content_type='application/json'):
            raw = value.encode() if content_type == 'text/event-stream' else json.dumps(value, ensure_ascii=False, allow_nan=False).encode()
            self.send_response(status)
            self.send_header('Content-Type', content_type + '; charset=utf-8')
            self.send_header('Content-Length', str(len(raw)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.end_headers()
            self.wfile.write(raw)

        def setup(self):
            super().setup()
            self.connection.settimeout(5)

        do_GET = dispatch
        do_POST = dispatch

    return ThreadingHTTPServer(('127.0.0.1', port), Handler)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--database', required=True)
    parser.add_argument('--clients-file', required=True)
    parser.add_argument('--port', type=int, default=8791)
    parser.add_argument('--phase2', action='store_true')
    args = parser.parse_args()
    path = Path(args.clients_file)
    if path.stat().st_mode & 0o077:
        raise SystemExit('Client configuration requires mode 0600')
    extension = None
    if args.phase2:
        from .phase2.http_bridge import dispatch
        extension = dispatch
    srv = server(args.database, json.loads(path.read_text()), args.port, extension=extension)
    try:
        srv.serve_forever()
    finally:
        srv.server_close()


if __name__ == '__main__':
    main()
