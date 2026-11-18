"""Client for the verified upstream /v1/runs contract; never starts Hermes."""
import re
from .local_model import Unavailable

HERMES_COMMIT = '4959268e312a21a361f248e49030d5f5df3984d5'


class HermesRuns:
    def __init__(self, transport, model, *, allow_live=False):
        self.http, self.model, self.allow_live = transport, model, allow_live

    def create(self, mission_id, context):
        if not self.allow_live:
            raise Unavailable('Live Hermes activation requires an approved isolated profile')
        return self.http('POST', '/v1/runs', {'model': self.model, 'input': context}, timeout=5,
                         headers={'Idempotency-Key': 'jarvis-' + mission_id})

    @staticmethod
    def path(run_id):
        if not isinstance(run_id, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,128}', run_id):
            raise ValueError('Invalid upstream run id')
        return '/v1/runs/' + run_id

    def status(self, run_id):
        return self.http('GET', self.path(run_id), timeout=5)

    def stop(self, run_id):
        if not self.allow_live:
            raise Unavailable('Live stop forwarding disabled')
        return self.http('POST', self.path(run_id) + '/stop', {}, timeout=5)

    def approve(self, run_id, request_id, choice):
        if not self.allow_live:
            raise Unavailable('Live approval forwarding disabled')
        if choice not in {'once', 'deny'} or not isinstance(request_id, str) or not 1 <= len(request_id) <= 256:
            raise PermissionError('Only exact once/deny approvals')
        return self.http('POST', self.path(run_id) + '/approval', {'request_id': request_id, 'choice': choice}, timeout=5)
