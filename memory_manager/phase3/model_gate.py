"""Laboratory-only bounded OpenAI relay. No upstream URL/provider from the model.

The network boundary must additionally deny Hermes direct access to the tunnel.
This module alone is not OS isolation. HTTP timeout is not GPU cancellation.
"""
from contextlib import closing
import hmac
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import hashlib
import json
import math
import threading
import time

from ..store import Memory, SECRET
from .. import missions
from ..phase2 import budgets
from ..phase2.bridge import execution_started
from ..phase2.local_model import Busy, Unavailable
from ..phase2.validation import loads, validate
from ..phase2.mcp import TOOLS, EXTRA
from .mcp import READ, SOURCES


MAX_BODY = 262144


def resident_mib(transport, model, digest, timeout=2):
    """(MiB held by OUR pinned model per Ollama /api/ps, diagnostic note). 0 when absent or unreadable."""
    try: rows = transport('GET', '/api/ps', timeout=timeout).get('models', [])
    except Exception as e: return 0, 'ps-error ' + type(e).__name__
    rows = rows if isinstance(rows, list) else []
    for m in rows:
        if isinstance(m, dict) and m.get('name') == model and m.get('digest') == digest and not m.get('remote_host'):
            v = m.get('size_vram')
            return (v // (1024 * 1024), 'own model resident') if type(v) is int and v > 0 else (0, 'own model, no size_vram')
    names = ','.join(str(m.get('name'))[:40] for m in rows if isinstance(m, dict))[:120]
    digests = ','.join(str(m.get('digest'))[:12] for m in rows if isinstance(m, dict))[:80]
    return 0, 'not resident (ps: %s / %s)' % (names or '-', digests or '-')


def counting_resident(sample, transport, model, digest, minimum_free_mib):
    """18.11: the VRAM our own loaded model holds is available to it (prod ebd39223: Kryptex ~1.1 GB +
    our model ~5.8 GB = 3.3 GB free, refused although everything fitted). Returns (sample, note)."""
    free = sample.get('free_mib') if isinstance(sample, dict) else None
    if type(free) not in (int, float) or not math.isfinite(free) or free >= minimum_free_mib: return sample, None
    held, note = resident_mib(transport, model, digest)
    return (dict(sample, free_mib=free + held) if held else sample), '%s, %s MiB' % (note, held)


def vram_available(sample, minimum_free_mib, now=None):
    """18.11 (User): mining may run in parallel (Kryptex uses ~1.2 GB VRAM at 100 % compute). Only the
    memory decides: fresh telemetry and enough free VRAM. Utilization and miner presence no longer block."""
    now = time.time() if now is None else now
    if not isinstance(sample, dict) or type(sample.get('observed_at')) not in (int, float) or not 0 <= now - sample['observed_at'] <= 15:
        raise Busy('Fresh GPU telemetry required')
    free = sample.get('free_mib')
    if type(free) not in (int, float) or not math.isfinite(free) or free < minimum_free_mib:
        raise Busy('GPU memory unavailable')


class Gate:
    def __init__(self, memory, principal, budget_id, mission_id, config, transport, telemetry,
                 *, max_calls=6, seconds=180):
        config.check()
        if config.protocol != 'ollama':
            raise ValueError('Pilot relay requires native Ollama upstream')
        if config.context_tokens > 64000 or config.max_output_tokens > 1024:
            raise ValueError('Pilot context/output ceiling')
        if not 1 <= max_calls <= 6 or not 0 < seconds <= 180:
            raise ValueError('Pilot bounds')
        self.path, self.principal = memory.path, principal
        self.bid, self.mid, self.cfg = budget_id, mission_id, config
        self.http, self.telemetry = transport, telemetry
        self.calls, self.seconds = max_calls, seconds
        self.started, self.lock = time.monotonic(), threading.Lock()
        self.previous = None   # (digest of tools+messages, message count, measured prompt tokens)

    def call(self, body):
        if not self.lock.acquire(blocking=False):
            raise Unavailable('Only one pilot request at a time')
        try:
            with closing(Memory(self.path)) as memory:
                return self._call(body, memory)
        finally:
            self.lock.release()

    @staticmethod
    def digest(tools, messages):
        return hashlib.sha256(json.dumps([tools, messages], ensure_ascii=False, sort_keys=True).encode()).hexdigest()

    def _call(self, body, memory):
        cfg = self.cfg
        mission = missions.get(memory, self.principal, self.mid)
        local_limit = mission['definition']['budget'].get('local_tokens', 0)
        account = memory.db.execute('SELECT * FROM p2_budgets WHERE id=? AND owner=?',
                                    (self.bid, self.principal.name)).fetchone()
        if type(local_limit) is not int or not 0 < local_limit <= 98304 or not account or not 0 < account['token_limit'] <= local_limit or account['monthly_remote_micros'] != 0:
            raise PermissionError('Explicit local mission quota and zero-remote account required')
        if mission['state'] in {'paused', 'cancelled', 'failed', 'completed', 'awaiting_approval'}:
            raise PermissionError('Mission not available for inference')
        started = execution_started(memory, self.mid, mission['created'])
        if time.time() - started >= mission['definition']['budget']['seconds']:
            raise PermissionError('Persistent mission deadline exhausted')
        if time.monotonic() - self.started >= self.seconds:
            raise PermissionError('Pilot time quota exhausted')
        calls = memory.db.execute('SELECT count(*) FROM p2_usage WHERE budget_id=? AND mission_id=?',
                                       (self.bid, self.mid)).fetchone()[0]
        if calls >= self.calls:
            raise PermissionError('Pilot call quota exhausted')
        allowed = {'model', 'messages', 'tools', 'tool_choice', 'parallel_tool_calls', 'temperature',
                   'max_tokens', 'max_completion_tokens', 'stream', 'stream_options', 'response_format', 'reasoning_effort'}
        if set(body) - allowed or body.get('model') != cfg.model or not isinstance(body.get('messages'), list):
            raise ValueError('Pinned model and bounded OpenAI envelope required')
        grants = mission['definition']['allowed_tools']
        names = set(READ) if 'memory.search' in grants else set()
        if 'memory.propose' in grants:
            names.add('jarvis_skill_propose')
        if 'memory.search' in grants:
            names.add('jarvis_skill_get')
        if 'sources.read' in grants:
            names |= SOURCES
        schemas = {t['name']: t['inputSchema'] for t in TOOLS}
        schemas.update({k: v[1] for k, v in EXTRA.items()})
        granted = {'mcp__jarvis__' + name: schemas[name] for name in names}
        advertised = set()
        for tool in body.get('tools', []):
            name = tool.get('function', {}).get('name')
            if name not in granted:
                raise PermissionError('Tool advertisement exceeds host mission grants')
            advertised.add(name)
        if body.get('reasoning_effort') not in (None, 'none', 'minimal', 'low', 'medium', 'high', 'xhigh'):
            raise ValueError('Unsupported reasoning hint')
        # Prompt size upper bound. A token is at least one UTF-8 byte, so bytes bound tokens; but
        # Hermes resends the whole history each turn (prod 18.11 a89250f9: ~15k tokens = 64 kB at the
        # 3rd-4th call). When this request extends the previous one of this gate (same tools, same
        # earlier messages), reuse the MEASURED prompt tokens of that prefix and count only the new
        # messages in bytes (+ template margin). Otherwise: bytes for everything.
        size = len(json.dumps(body, ensure_ascii=False).encode())
        estimate = size
        if self.previous and len(body['messages']) > self.previous[1]:
            n = self.previous[1]
            if self.digest(body.get('tools'), body['messages'][:n]) == self.previous[0]:
                added = body['messages'][n:]
                estimate = min(size, self.previous[2] + len(json.dumps(added, ensure_ascii=False).encode()) + 64 * len(added) + 256)
        if estimate + cfg.max_output_tokens > cfg.context_tokens:
            raise ValueError('Context admission limit')
        vram_available(self.telemetry(), cfg.min_free_mib)
        tag = next((m for m in self.http('GET', '/api/tags')['models'] if m.get('name') == cfg.model), {})
        if tag.get('digest') != cfg.digest or tag.get('remote_host') or tag.get('remote_model'):
            raise Unavailable('Installed local digest mismatch')
        # Native Ollama gives control of context and model unload, including tool calls.
        messages = loads(json.dumps(body['messages']))
        output_limit = cfg.max_output_tokens
        for field in ('max_tokens', 'max_completion_tokens'):
            if field in body:
                if type(body[field]) is not int or body[field] <= 0:
                    raise ValueError('Positive output limit required')
                output_limit = min(output_limit, body[field])
        for message in messages:
            for tool in message.get('tool_calls', []):
                function = tool['function']
                if isinstance(function.get('arguments'), str):
                    function['arguments'] = loads(function['arguments'])
        request = {'model': cfg.model, 'messages': messages, 'stream': False,
                   'options': {'num_ctx': cfg.context_tokens, 'num_predict': output_limit,
                               'temperature': 0, 'seed': 7}, 'keep_alive': 0}
        if cfg.think is not None:
            request['think'] = cfg.think
        if body.get('tools'):
            request['tools'] = body['tools']
        if body.get('tool_choice') not in (None, 'auto') or body.get('parallel_tool_calls') not in (None, False):
            raise ValueError('Tool choice overrides not implemented by pilot relay')
        if body.get('response_format'):
            fmt = body['response_format']
            if fmt.get('type') == 'json_schema':
                request['format'] = fmt['json_schema']['schema']
            elif fmt.get('type') == 'json_object':
                request['format'] = 'json'
            else:
                raise ValueError('Unsupported response format')
        # Prod 17.11 (0d1c6c51): reserving the whole 64k context per call refused the 4th-5th call of a
        # 98k mission budget although ~30k were used. Reserve what this call can use: request bytes
        # (>= tokens, conservative) + output limit + template margin, capped at the context.
        cid = budgets.reserve(memory, self.principal, self.bid, self.mid, cfg.model,
                              tokens=min(cfg.context_tokens, estimate + output_limit + 2048))
        start = time.monotonic()
        remaining = min(self.seconds - (time.monotonic() - self.started),
                        mission['definition']['budget']['seconds'] - (time.time() - started))
        if remaining <= 0:
            raise PermissionError('Pilot deadline exhausted before dispatch')
        result = self.http('POST', '/api/chat', request, timeout=min(cfg.timeout_seconds, remaining))
        if not result.get('done') or result.get('done_reason') != 'stop':
            raise ValueError('Incomplete model response')
        it, ot = result.get('prompt_eval_count'), result.get('eval_count')
        if type(it) is not int or type(ot) is not int or min(it, ot) < 0:
            raise ValueError('Missing token usage')
        budgets.settle(memory, self.principal, cid, used_tokens=it + ot,
                       actual_remote_micros=0, latency=time.monotonic() - start)
        if it + output_limit > cfg.context_tokens:
            self.previous = None
            raise ValueError('Context overflow (prompt possibly truncated)')
        self.previous = (self.digest(body.get('tools'), body['messages']), len(body['messages']), it)
        if 'format' in request:
            value = loads(result['message'].get('content', ''))
            if isinstance(request['format'], dict):
                validate(value, request['format'])
            elif not isinstance(value, dict):
                raise ValueError('JSON object required')
        message = {'role': 'assistant', 'content': result['message'].get('content', '')}
        if result['message'].get('tool_calls'):
            calls = result['message']['tool_calls']
            if not isinstance(calls, list) or len(calls) > 4:
                raise PermissionError('Tool batch limit')
            for call in calls:
                function = call['function']
                name = function['name']
                if name not in advertised:
                    raise PermissionError('Unadvertised model tool denied: ' + str(name)[:80])
                validate(function['arguments'], granted[name])
            message['tool_calls'] = [{'id': 'pilot-' + cid + '-' + str(i), 'type': 'function',
                'function': {'name': t['function']['name'],
                             'arguments': json.dumps(t['function']['arguments'], ensure_ascii=False)}}
                for i, t in enumerate(result['message']['tool_calls'])]
        return {'id': cid, 'object': 'chat.completion', 'created': int(time.time()), 'model': cfg.model,
                'choices': [{'index': 0, 'message': message,
                             'finish_reason': 'tool_calls' if message.get('tool_calls') else 'stop'}],
                'usage': {'prompt_tokens': it, 'completion_tokens': ot, 'total_tokens': it + ot}}


def server(gate, token, port=0):
    if not isinstance(token, str) or len(token) < 32:
        raise ValueError('Independent laboratory authentication required')

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_): pass
        def do_GET(self):
            if not hmac.compare_digest(self.headers.get('Authorization', ''), 'Bearer ' + token):
                return self.reply(401, {'error': 'Authentication required'})
            if self.path != '/v1/models':
                return self.reply(404, {'error': 'Pilot endpoint denied'})
            return self.reply(200, {'object': 'list', 'data': [{'id': gate.cfg.model,
                              'object': 'model', 'owned_by': 'local-laboratory',
                              'context_length': gate.cfg.context_tokens}]})
        def do_POST(self):
            if not hmac.compare_digest(self.headers.get('Authorization', ''), 'Bearer ' + token):
                return self.reply(401, {'error': 'Authentication required'})
            if self.path != '/v1/chat/completions':
                return self.reply(404, {'error': 'Pilot endpoint denied'})
            try:
                size = int(self.headers.get('Content-Length', 0))
                # Transport ceiling only; the context bound is Gate._call (prod 18.11: 64000 refused
                # a 15k-token history as 'Body limit').
                if not 0 < size <= MAX_BODY or self.headers.get('Transfer-Encoding'):
                    raise ValueError('Body limit')
                body = loads(self.rfile.read(size))
                result = gate.call(body)
                if body.get('stream'):
                    chunk = {k: v for k, v in result.items() if k not in {'choices', 'usage'}}
                    chunk['object'] = 'chat.completion.chunk'
                    choice = result['choices'][0]
                    delta = dict(choice['message'])
                    if 'tool_calls' in delta:
                        delta['tool_calls'] = [dict(t, index=i) for i, t in enumerate(delta['tool_calls'])]
                    chunk['choices'] = [{'index': 0, 'delta': delta, 'finish_reason': None}]
                    final = {**chunk, 'usage': result['usage'], 'choices': [{'index': 0, 'delta': {}, 'finish_reason': choice['finish_reason']}]}
                    raw = 'data: ' + json.dumps(chunk) + '\n\ndata: ' + json.dumps(final) + '\n\ndata: [DONE]\n\n'
                    return self.reply(200, raw, 'text/event-stream')
                return self.reply(200, result)
            except PermissionError as exc:
                # Journal the exact refusal (reason and tool name, never content or tokens);
                # the client still only learns the generic 403.
                reason = str(exc)[:160]
                print(json.dumps({'event': 'model-gate-refused', 'reason': '[filtered]' if SECRET.search(reason) else reason}), flush=True)
                return self.reply(403, {'error': 'Pilot quota or mission denied'})
            except (ValueError, TypeError, KeyError) as exc:
                # Prod 17.11: these refusals were not journaled. Reason only (fixed texts), never content.
                reason = (type(exc).__name__ + ': ' + str(exc))[:160]
                print(json.dumps({'event': 'model-gate-invalid', 'reason': '[filtered]' if SECRET.search(reason) else reason}), flush=True)
                return self.reply(400, {'error': 'Invalid pilot request or response'})
            except Exception:
                return self.reply(503, {'error': 'Local inference unavailable; no fallback'})

        def reply(self, status, value, kind='application/json'):
            raw = (value if kind == 'text/event-stream' else json.dumps(value)).encode()
            self.send_response(status)
            self.send_header('Content-Type', kind)
            self.send_header('Content-Length', str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def setup(self):
            super().setup()
            self.connection.settimeout(5)

    return ThreadingHTTPServer(('127.0.0.1', port), Handler)
