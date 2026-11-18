"""Mission tools over the real sources (Home Assistant, InfluxDB 3). Each read becomes a citable canonical measurement.

The ingesting principal is host-selected (never the model): kind 'measurement',
status 'observed', source.ref built here. Rows come back in the memory-search shape
(memory_id, revision_id, source.ref, content) so the existing receipts, projection
and report-quality check apply unchanged.
"""
import time
from ..store import Principal, uid

TOOLS = {
    'source.ha.states': ('ha', 'states', {'query', 'domain', 'limit'}),
    'source.ha.history': ('ha', 'history', {'entity_id', 'hours'}),
    'source.influx.entities': ('influx', 'entities', {'query', 'database', 'limit'}),
    'source.influx.series': ('influx', 'series', {'entity_id', 'days', 'every_minutes', 'database'}),
}
REQUIRED = {'source.ha.history': {'entity_id', 'hours'}, 'source.influx.series': {'entity_id', 'days'}}
PREFIXES = ('ha://', 'influx://')


def stamp(ts):
    return time.strftime('%Y%m%dT%H%MZ', time.gmtime(ts))


def ref_for(name, args, result, ts):
    if name == 'source.ha.states':
        return 'ha://states?q=%s&domain=%s@%s' % (args.get('query', ''), args.get('domain', ''), stamp(ts))
    if name == 'source.ha.history':
        return 'ha://%s/history/%dh@%s' % (result['entity_id'], args['hours'], stamp(ts))
    if name == 'source.influx.entities':
        return 'influx://%s/entities?q=%s@%s' % (result['database'], args.get('query', ''), stamp(ts))
    return 'influx://%s/%s/%dd/%dm@%s' % (result['database'], result['entity_id'], args['days'], result['window_minutes'], stamp(ts))


class SourceTools:
    def __init__(self, memory, owner, readers, *, clock=time.time):
        self.m, self.readers, self.clock = memory, readers, clock
        self.p = Principal(owner, frozenset({'private'}), frozenset({'reader', 'proposer', 'ingester'}), 'source-reader')

    def available(self):
        return sorted(n for n, (src, _, _) in TOOLS.items() if src in self.readers)

    def call(self, name, args):
        if name not in TOOLS: raise PermissionError('Unknown source tool')
        src, method, fields = TOOLS[name]
        if src not in self.readers: raise PermissionError('Source not configured: ' + src)
        if not isinstance(args, dict) or set(args) - fields or not REQUIRED.get(name, set()) <= set(args):
            raise ValueError('Source tool fields: ' + ', '.join(sorted(fields)))
        ts = self.clock()
        result = getattr(self.readers[src], method)(**args)
        ref = ref_for(name, args, result, ts)[:1000]
        subject = (result.get('entity_id') or 'Home Assistant' if src == 'ha' else result.get('entity_id') or 'InfluxDB')[:200]
        ids = self.m.ingest(self.p, 'source-read-' + uid(), {'kind': 'measurement', 'ref': ref, 'observed_at': ts},
                            [{'type': 'knowledge', 'subject': subject, 'predicate': name, 'content': result,
                              'status': 'observed', 'confidence': 1.0}])
        row = self.m.db.execute('SELECT current_revision FROM mm_memories WHERE id=?', (ids[0],)).fetchone()
        return [{'memory_id': ids[0], 'revision_id': row[0], 'source': {'ref': ref, 'kind': 'measurement'},
                 'subject': subject, 'content': result,
                 'citation': 'Cite source.ref verbatim: ' + ref}]
