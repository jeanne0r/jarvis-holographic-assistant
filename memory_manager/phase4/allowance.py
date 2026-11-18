"""Controller-only allowance for one expressly approved, bounded Windows pilot."""
import json
import math
import os
import stat
import time
import fcntl


def consume(path, kind, *, now=None):
    """Reserve before dispatch, including failures. Corrupt/missing evidence fails closed."""
    if kind not in {'calls', 'missions'}: raise ValueError('Unknown pilot allowance')
    now = time.time() if now is None else now
    fd = os.open(path, os.O_RDWR | os.O_NOFOLLOW)
    with os.fdopen(fd, 'r+') as f:
        info = os.fstat(f.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_mode & 0o077 or info.st_uid != os.getuid():
            raise PermissionError('Private host-owned pilot allowance required')
        fcntl.flock(f.fileno(), fcntl.LOCK_EX)
        raw = f.read(4097)
        if len(raw) > 4096: raise PermissionError('Invalid pilot allowance')
        value = json.loads(raw)
        if value.get('closed', False) is not False:raise PermissionError('Pilot approval window closed')
        start, end = value['started_at'], value['expires_at']
        if (type(start) not in (int, float) or type(end) not in (int, float)
                or not math.isfinite(start) or not math.isfinite(end)
                or not 0 < end - start <= 1800 or not start <= now < end):
            raise PermissionError('Pilot approval window expired or invalid')
        caps = value.get('limits', {'calls':24,'missions':4})
        if not isinstance(caps,dict) or set(caps)!={'calls','missions'} or any(type(caps[k]) is not int or not 1<=caps[k]<=maximum for k,maximum in [('calls',24),('missions',4)]):
            raise PermissionError('Host limits may only narrow pilot caps')
        for field, cap in caps.items():
            if type(value[field]) is not int or not 0 <= value[field] <= cap:
                raise PermissionError('Invalid pilot counter')
        if value[kind] >= caps[kind]:
            raise PermissionError('Approved pilot allowance exhausted')
        value[kind] += 1
        f.seek(0); json.dump(value, f); f.truncate(); f.flush(); os.fsync(f.fileno())
        return value
