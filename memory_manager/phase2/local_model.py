"""Private-only Ollama adapter, strict output, admission gate, no fallback/pull."""
from dataclasses import dataclass
import ipaddress
import json
import math
import socket
import time
import urllib.error
import urllib.parse
import urllib.request
from .validation import loads, validate


class Unavailable(RuntimeError):
    pass


class Busy(Unavailable):
    pass


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise Unavailable('Redirect refused')


class PrivateHTTP:
    def __init__(self, base_url, token=None):
        url = urllib.parse.urlsplit(base_url)
        try: ip = ipaddress.ip_address(url.hostname or '')
        except ValueError: raise ValueError('Use an explicit private IP; DNS endpoints are not accepted')
        private = ip.is_loopback or (ip.version == 4 and any(ip in ipaddress.ip_network(n) for n in ('10.0.0.0/8', '172.16.0.0/12', '192.168.0.0/16', '100.64.0.0/10'))) or (ip.version == 6 and ip in ipaddress.ip_network('fc00::/7'))
        if url.scheme not in {'http', 'https'} or not private or url.username or url.password or url.query or url.fragment or url.path not in {'', '/'}:
            raise ValueError('Private origin only')
        self.base, self.token = base_url.rstrip('/'), token
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())

    def __call__(self, method, path, body=None, *, timeout=5, headers=None):
        if not path.startswith('/') or path.startswith('//') or '\\' in path:
            raise ValueError('Invalid endpoint path')
        hdr = {'Content-Type': 'application/json', **(headers or {})}
        if self.token: hdr['Authorization'] = 'Bearer ' + self.token
        request = urllib.request.Request(self.base + path, method=method, headers=hdr,
                                         data=None if body is None else json.dumps(body, allow_nan=False).encode())
        try:
            with self.opener.open(request, timeout=timeout) as response:
                raw = response.read(1000001)
                if len(raw) > 1000000: raise Unavailable('Response limit')
                return loads(raw)
        except (urllib.error.URLError, TimeoutError, socket.timeout, OSError) as exc:
            # Never include URLs, credentials, response bodies or private prompts.
            raise Unavailable('Private endpoint unavailable') from None


@dataclass(frozen=True)
class ModelConfig:
    model: str
    digest: str
    context_tokens: int = 8192
    max_output_tokens: int = 768
    timeout_seconds: float = 30
    protocol: str = 'ollama'
    min_free_mib: int = 6000
    think: bool | None = None

    def check(self):
        if self.think is not None and (type(self.think) is not bool or self.protocol != 'ollama'):
            raise ValueError('Thinking override requires native Ollama and a boolean')
        if not self.model or 'cloud' in self.model.lower() or not self.digest or not 1024 <= self.context_tokens <= 64000 or not 16 <= self.max_output_tokens <= 4096 or not 0 < self.timeout_seconds <= 60 or self.protocol not in {'ollama', 'openai_compatible'}:
            raise ValueError('Invalid local model configuration')


def gpu_available(sample, minimum_free_mib, now=None):
    now = time.time() if now is None else now
    if not isinstance(sample, dict) or type(sample.get('observed_at')) not in (int, float) or not 0 <= now - sample['observed_at'] <= 15:
        raise Busy('Fresh GPU telemetry required')
    if sample.get('miner_running') is not False or not isinstance(sample.get('utilization'), (float, int)) or not 0 <= sample['utilization'] < 20:
        raise Busy('GPU occupied or mining status unknown')
    free = sample.get('free_mib')
    if type(free) not in (int, float) or not math.isfinite(free) or free < minimum_free_mib:
        raise Busy('GPU memory unavailable')


class LocalModel:
    def __init__(self, config, transport, telemetry):
        config.check()
        self.config, self.http, self.telemetry = config, transport, telemetry

    def generate(self, messages, schema, *, reserved_tokens):
        cfg = self.config
        # UTF-8 byte count is a conservative admission heuristic, not a tokenizer.
        prompt_bytes = len(json.dumps(messages, ensure_ascii=False).encode()) + len(json.dumps(schema).encode())
        if prompt_bytes + cfg.max_output_tokens > cfg.context_tokens:
            raise ValueError('Context admission limit')
        if reserved_tokens < prompt_bytes + cfg.max_output_tokens:
            raise ValueError('Token reservation required')
        before = self.telemetry()
        gpu_available(before, cfg.min_free_mib)
        tags = self.http('GET', '/api/tags', timeout=3)
        installed = next((m for m in tags.get('models', []) if m.get('name') == cfg.model), None)
        if not installed or installed.get('digest') != cfg.digest or installed.get('remote_model') or installed.get('remote_host'):
            raise Unavailable('Pinned local model absent or changed')
        if cfg.protocol == 'ollama':
            path = '/api/chat'
            body = {'model': cfg.model, 'messages': messages, 'stream': False, 'format': schema,
                    'options': {'num_ctx': cfg.context_tokens, 'num_predict': cfg.max_output_tokens, 'temperature': 0, 'seed': 7}, 'keep_alive': 0}
            if cfg.think is not None:
                body['think'] = cfg.think
        else:
            path = '/v1/chat/completions'
            body = {'model': cfg.model, 'messages': messages, 'stream': False, 'max_tokens': cfg.max_output_tokens,
                    'temperature': 0, 'response_format': {'type': 'json_schema', 'json_schema': {'name': 'jarvis_proposal', 'strict': True, 'schema': schema}}}
        started = time.monotonic()
        response = self.http('POST', path, body, timeout=cfg.timeout_seconds)
        if cfg.protocol == 'ollama':
            if not response.get('done') or response.get('done_reason') == 'length':
                raise ValueError('Incomplete local response')
            raw = response['message']['content']
            input_tokens, output_tokens = response.get('prompt_eval_count', 0), response.get('eval_count', 0)
            duration_ns = response.get('eval_duration', 0)
        else:
            choice = response['choices'][0]
            if choice.get('finish_reason') != 'stop': raise ValueError('Incomplete local response')
            raw = choice['message']['content']
            usage = response.get('usage', {})
            input_tokens, output_tokens = usage.get('prompt_tokens', 0), usage.get('completion_tokens', 0)
            duration_ns = 0
        if type(input_tokens) is not int or type(output_tokens) is not int or min(input_tokens, output_tokens) < 0 or input_tokens + output_tokens > reserved_tokens:
            raise ValueError('Provider usage violates reservation')
        value = validate(loads(raw), schema)
        elapsed = time.monotonic() - started
        after = self.telemetry()
        return value, {'model': cfg.model, 'digest': cfg.digest, 'input_tokens': input_tokens, 'output_tokens': output_tokens,
                       'latency_seconds': elapsed, 'gpu_window_seconds': elapsed, 'gpu_time_measured': False,
                       'tokens_per_second': output_tokens / (duration_ns / 1e9) if duration_ns else None,
                       'vram_before_mib': before.get('used_mib'), 'vram_after_mib': after.get('used_mib'),
                       'api_cost_micros': 0, 'fallback': False}
