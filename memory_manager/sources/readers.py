"""Host-side readers. Each one exposes only fixed, read-only requests.

Home Assistant has no read-only token: any token can call services. InfluxDB 3 Core has
only admin tokens. The guarantee is therefore this module: HA = GET on /api/states and
/api/history/period only, paths built from a validated entity_id; Influx = GET on
/api/v3/query_influxql only, query text built here from validated values.
"""
import json, math, re, ssl, time, urllib.parse, urllib.request
from datetime import datetime, timezone

from ..store import SECRET

ENTITY = re.compile(r'[a-z_]{1,32}\.[a-z0-9_]{1,128}')
BUCKET = re.compile(r'[A-Za-z0-9_.-]{1,64}')
MAX_BYTES = 4_000_000
KEEP_ATTRIBUTES = ('friendly_name', 'unit_of_measurement', 'device_class', 'state_class')


class SourceUnavailable(RuntimeError):
    pass


def iso(ts):
    return datetime.fromtimestamp(ts, timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def entity(value):
    if not isinstance(value, str) or not ENTITY.fullmatch(value): raise ValueError('entity_id like sensor.name required')
    return value


def bounded_int(value, low, high, name):
    if type(value) is not int or not low <= value <= high: raise ValueError('%s must be an integer in [%d, %d]' % (name, low, high))
    return value


def clean(text, limit=200):
    """Free text from a source, truncated; anything shaped like a credential is dropped."""
    text = str(text)[:limit]
    return '[masqué]' if SECRET.search(text) else text


class Http:
    """GET/POST to one pinned base URL, no proxy, bounded body, no redirect follow."""
    def __init__(self, base, headers, *, cafile=None, timeout=15, opener=None):
        u = urllib.parse.urlsplit(base)
        if u.scheme not in ('http', 'https') or not u.hostname or u.path not in ('', '/') or u.query or u.username:
            raise ValueError('Plain base URL required')
        self.base, self.headers, self.timeout = base.rstrip('/'), dict(headers), timeout
        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, *a, **k): return None
        handlers = [urllib.request.ProxyHandler({}), NoRedirect()]
        if u.scheme == 'https': handlers.append(urllib.request.HTTPSHandler(context=ssl.create_default_context(cafile=cafile)))
        self.opener = opener or urllib.request.build_opener(*handlers)

    def __call__(self, method, path, *, query=None, body=None, headers=None):
        if method not in ('GET', 'POST') or not path.startswith('/') or '..' in path: raise PermissionError('Fixed request only')
        url = self.base + urllib.parse.quote(path, safe='/:._-') + ('?' + urllib.parse.urlencode(query) if query else '')
        req = urllib.request.Request(url, data=body, method=method, headers={**self.headers, **(headers or {})})
        try:
            with self.opener.open(req, timeout=self.timeout) as r:
                raw = r.read(MAX_BYTES + 1)
        except Exception as e:
            # Never echo the request (it may carry the token in headers); type only.
            raise SourceUnavailable('Source unreachable or refused (%s)' % type(e).__name__) from None
        if len(raw) > MAX_BYTES: raise SourceUnavailable('Source answer too large')
        return raw


def summarize(points, *, max_points=48):
    """points: [(ts, value)] sorted. Numeric → stats + downsampled series; text → transitions."""
    numeric = []
    for ts, v in points:
        try:
            f = float(v)
            if math.isfinite(f): numeric.append((ts, f))
        except (TypeError, ValueError):
            pass
    out = {'count': len(points)}
    if points: out.update(first=iso(points[0][0]), last=iso(points[-1][0]))
    if numeric and len(numeric) >= len(points) / 2:
        vals = [v for _, v in numeric]
        step = max(1, math.ceil(len(numeric) / max_points))
        out.update(kind='numeric', min=round(min(vals), 4), max=round(max(vals), 4), mean=round(sum(vals) / len(vals), 4),
                   last_value=round(vals[-1], 4), unavailable=len(points) - len(numeric),
                   series=[[iso(numeric[i][0]), round(sum(v for _, v in numeric[i:i + step]) / len(numeric[i:i + step]), 4)]
                           for i in range(0, len(numeric), step)],
                   series_note='moyenne par paquet de %d point(s)' % step if step > 1 else 'points bruts')
    else:
        counts = {}
        for _, v in points: counts[clean(v, 64)] = counts.get(clean(v, 64), 0) + 1
        out.update(kind='states', states=dict(sorted(counts.items(), key=lambda kv: -kv[1])[:12]),
                   transitions=[[iso(ts), clean(v, 64)] for ts, v in points[-max_points:]])
    return out


class HomeAssistant:
    def __init__(self, http):
        self.http = http

    def _json(self, path, query=None):
        try: return json.loads(self.http('GET', path, query=query))
        except ValueError: raise SourceUnavailable('Home Assistant answer is not JSON') from None

    def states(self, query='', domain='', limit=40):
        if not isinstance(query, str) or len(query) > 80 or not isinstance(domain, str) or not re.fullmatch(r'[a-z_]{0,32}', domain):
            raise ValueError('Short query and domain required')
        limit = bounded_int(limit, 1, 100, 'limit')
        words = [w for w in re.findall(r'\w+', query.lower()) if w][:6]
        rows = []
        for s in self._json('/api/states'):
            eid = s.get('entity_id', '')
            if domain and not eid.startswith(domain + '.'): continue
            attrs = s.get('attributes') or {}
            hay = (eid + ' ' + str(attrs.get('friendly_name', ''))).lower()
            if words and not all(w in hay for w in words): continue
            rows.append({'entity_id': eid, 'state': clean(s.get('state'), 120), 'last_changed': clean(s.get('last_changed'), 40),
                         **{k: clean(attrs[k], 120) for k in KEEP_ATTRIBUTES if k in attrs}})
        rows.sort(key=lambda r: r['entity_id'])
        return {'matched': len(rows), 'items': rows[:limit], 'truncated': len(rows) > limit}

    def history(self, entity_id, hours, now=None):
        entity_id, hours = entity(entity_id), bounded_int(hours, 1, 24 * 31, 'hours')
        end = now or time.time(); start = end - hours * 3600
        data = self._json('/api/history/period/' + iso(start), {
            'filter_entity_id': entity_id, 'end_time': iso(end), 'minimal_response': '', 'no_attributes': ''})
        rows = data[0] if data and isinstance(data[0], list) else []
        points = []
        for r in rows:
            t = r.get('last_changed') or r.get('last_updated')
            try: points.append((datetime.fromisoformat(str(t).replace('Z', '+00:00')).timestamp(), r.get('state')))
            except ValueError: continue
        points.sort()
        return {'entity_id': entity_id, 'from': iso(start), 'to': iso(end), **summarize(points),
                'note': "Home Assistant ne garde l'historique détaillé que quelques jours (recorder) ; au-delà, utiliser InfluxDB."}


def influxql_string(value):
    return "'" + value.replace('\\', '\\\\').replace("'", "\\'") + "'"


class Influx:
    """InfluxDB 3 Core (prod 17.11: 3.12.1) as fed by the Home Assistant integration through the
    v2 write API: database = HA bucket, table = unit (or entity_id), tags domain/entity_id, field value.
    Core only has ADMIN tokens: the read-only guarantee is this class (GET /api/v3/query_influxql only,
    query text built here from validated values). Checked on a local 3.12.1: DDL/DML are refused there too."""
    MAX_POINTS = 5000

    def __init__(self, http, databases):
        if not databases or any(not isinstance(d, str) or not BUCKET.fullmatch(d) for d in databases):
            raise ValueError('Influx database allowlist required')
        self.http, self.databases = http, list(databases)

    def _db(self, database):
        database = database or self.databases[0]
        if database not in self.databases: raise PermissionError('Database not allowed')
        return database

    def _query(self, influxql, database):
        raw = self.http('GET', '/api/v3/query_influxql', query={'db': database, 'q': influxql, 'format': 'json'})
        try: rows = json.loads(raw)
        except ValueError: raise SourceUnavailable('InfluxDB answer is not JSON') from None
        if not isinstance(rows, list): raise SourceUnavailable('Unexpected InfluxDB answer')
        return rows

    def entities(self, query='', database='', limit=60):
        database = self._db(database); limit = bounded_int(limit, 1, 200, 'limit')
        if not isinstance(query, str) or len(query) > 80: raise ValueError('Short query required')
        words = re.findall(r'\w+', query.lower())[:6]
        found = sorted({(str(r.get('value', '')), str(r.get('iox::measurement', ''))) for r in self._query('SHOW TAG VALUES WITH KEY = "entity_id"', database)} - {('', '')})
        found = [(e, m) for e, m in found if all(w in (e + ' ' + m).lower() for w in words)]
        return {'database': database, 'matched': len(found), 'truncated': len(found) > limit,
                'items': [{'entity': clean(e, 128), 'table': clean(m, 128)} for e, m in found[:limit]],
                'note': "entity = partie après le point de l'entité HA (sensor.x -> x) ; table = unité ou entité."}

    def series(self, entity_id, days, every_minutes=60, database='', now=None):
        eid = entity(entity_id); domain, object_id = eid.split('.', 1)
        days, every = bounded_int(days, 1, 3660, 'days'), bounded_int(every_minutes, 1, 10080, 'every_minutes')
        every = max(every, math.ceil(days * 1440 / self.MAX_POINTS))       # bounded answer, whatever the range
        database = self._db(database)
        q = ('SELECT mean("value") FROM /.*/ WHERE "entity_id" = %s AND "domain" = %s AND time > now() - %dd GROUP BY time(%dm) fill(none)'
             % (influxql_string(object_id), influxql_string(domain), days, every))
        points, tables = [], set()
        for r in self._query(q, database):
            try: points.append((datetime.fromisoformat(str(r['time']).replace('Z', '+00:00')).replace(tzinfo=timezone.utc).timestamp(), r['mean']))
            except (KeyError, ValueError, TypeError): continue
            tables.add(str(r.get('iox::measurement', '')))
        points.sort()
        end = now or time.time()
        return {'entity_id': eid, 'database': database, 'table': clean(','.join(sorted(tables)), 128), 'from': iso(end - days * 86400), 'to': iso(end),
                'window_minutes': every, **summarize(points)}


def load(cfg):
    """cfg: parsed private sources config. Missing sections simply disable that source."""
    out = {}
    if cfg.get('homeAssistant'):
        c = cfg['homeAssistant']
        out['ha'] = HomeAssistant(Http(c['url'], {'Authorization': 'Bearer ' + c['token']}, cafile=c.get('cafile')))
    if cfg.get('influx'):
        c = cfg['influx']
        out['influx'] = Influx(Http(c['url'], {'Authorization': 'Bearer ' + c['token']}, cafile=c.get('cafile')), c['databases'])
    return out
