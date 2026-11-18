"""Fixed host-selected pilot capabilities; reuse the existing memory protocol."""
import argparse
import json
from pathlib import Path
import sys

from ..phase2.local_model import PrivateHTTP
from ..phase2.mcp import dispatch as memory_dispatch
from ..phase2.mcp import EXTRA, TOOLS
from ..phase2.validation import validate

READ = frozenset({'jarvis_memory_audit', 'jarvis_memory_knowledge', 'jarvis_memory_search', 'jarvis_memory_history', 'jarvis_memory_project',
                  'jarvis_memory_experiences', 'jarvis_memory_contradictions', 'jarvis_skill_get'})
SOURCES = frozenset({'jarvis_ha_states', 'jarvis_ha_history', 'jarvis_influx_entities', 'jarvis_influx_series'})


def dispatch(message, http, *, skill_candidate=False, audit=None):
    allowed = READ | SOURCES | ({'jarvis_skill_propose', 'jarvis_skill_get'} if skill_candidate else set())
    call = message.get('method') == 'tools/call'
    name = message.get('params', {}).get('name')
    def rejected(reason):
        # Never record arguments, credentials or arbitrary attacker tool names.
        if audit: audit({'tool': name if name in allowed else 'ungranted', 'outcome': reason})
        return {'jsonrpc': '2.0', 'id': message['id'],
                'error': {'code': -32602, 'message': reason}}
    if call and name not in allowed:
        if 'id' not in message:
            return None
        return rejected('CAPABILITY_DENIED')
    if call and 'id' in message:
        schemas = {t['name']: t['inputSchema'] for t in TOOLS}
        schemas.update({k: v[1] for k, v in EXTRA.items()})
        try:
            validate(message['params'].get('arguments', {}), schemas[name])
        except (ValueError, TypeError):
            return rejected('ARGUMENT_SCHEMA_REJECTED')
    response = memory_dispatch(message, http)
    if call and response:
        if 'error' in response:
            return rejected('MEMORY_DENIED_OR_UNAVAILABLE')
        if audit: audit({'tool': name, 'outcome': 'accepted'})
    if message.get('method') == 'tools/list' and response:
        response['result']['tools'] = [t for t in response['result']['tools'] if t['name'] in allowed]
    return response


def main(*, token_reader=None):
    from ..mcp_utf8 import configure_stdio
    configure_stdio()
    parser = argparse.ArgumentParser()
    parser.add_argument('--token-file', required=True)
    parser.add_argument('--port', type=int, default=8792)
    parser.add_argument('--skill-candidate', action='store_true')
    args = parser.parse_args()
    path = Path(args.token_file)
    if token_reader is None:
        if path.stat().st_mode & 0o077:
            raise SystemExit('Token file requires mode 0600')
        token = path.read_text().strip()
    else:
        token = token_reader(path)
    http = PrivateHTTP('http://127.0.0.1:' + str(args.port), token)
    for line in sys.stdin:
        if len(line) > 64000:
            continue
        try:
            result = dispatch(json.loads(line), http, skill_candidate=args.skill_candidate,
                              audit=lambda event: print(json.dumps(event), file=sys.stderr, flush=True))
        except Exception:
            result = {'jsonrpc': '2.0', 'id': None, 'error': {'code': -32700, 'message': 'Invalid JSON'}}
        if result is not None:
            print(json.dumps(result), flush=True)


if __name__ == '__main__':
    main()
