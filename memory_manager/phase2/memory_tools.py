"""Controlled Hermes memory capabilities. Text never becomes a tool grant."""
import time
from ..store import encode, digest


class MemoryTools:
    def __init__(self, memory, principal, mission_id=None, *, searcher=None):
        self.m, self.p, self.mid = memory, principal, mission_id
        self.search = (lambda q, **kw: searcher(memory, principal, q, **kw)) if searcher else (lambda q, **kw: memory.search(principal, q, **kw))

    def call(self, name, args):
        allowed = {'memory.audit', 'memory.knowledge', 'memory.search', 'memory.history', 'memory.project', 'memory.experiences', 'memory.propose', 'memory.contradictions', 'skill.propose', 'skill.get', 'mission.result'}
        if name not in allowed or len(encode(args)) > 8000:
            raise PermissionError('Tool denied')
        if name == 'memory.audit':
            if set(args)!={'q'}:raise ValueError('Read-only audit fields')
            from ..phase6.memory_audit import audit
            return audit(self.m,self.p,args['q'],searcher=self.search)
        if name == 'memory.knowledge':
            from .validation import obj, TEXT, validate
            validate(args, obj({'q': TEXT}))
            return self.search(args['q'], memory_type='knowledge')
        if name == 'memory.search':
            return self.search(args['q'])
        if name == 'memory.history':
            return self.m.history(self.p, args['memory_id'])
        if name == 'skill.get':
            from .skill_registry import get
            if set(args) != {'name', 'version'}: raise ValueError('Skill lookup fields')
            from .validation import obj, TEXT, validate
            validate(args, obj({'name': TEXT, 'version': {'type': 'integer', 'minimum': 1}}))
            return get(self.m, self.p, args['name'], args['version'])
        if name in {'memory.project', 'memory.experiences', 'memory.contradictions'}:
            rows = self.search(args.get('q', ''), memory_type={'memory.project': 'project', 'memory.experiences': 'episode'}.get(name), subject=args.get('subject'))
            return [r for r in rows if r['contradictions']] if name == 'memory.contradictions' else rows
        if name == 'mission.result':
            if not self.mid: raise PermissionError('Mission binding required')
            from ..missions import get
            mission = get(self.m, self.p, self.mid)
            if mission['owner'] != self.p.name: raise PermissionError('Owner required')
            args = {'key': 'mission-result-' + self.mid, 'reference': 'mission://' + self.mid, 'candidate': {
                'type': 'episode', 'subject': mission['definition']['objective'][:200], 'predicate': 'reported_outcome', 'content': args}}
        if name == 'skill.propose':
            from .skill_registry import propose
            return propose(self.m, self.p, args['spec'], args['sources'], scope=args.get('scope', 'private'))
        if set(args) - {'key', 'reference', 'candidate', 'scope'}: raise ValueError('Proposal fields')
        c = args['candidate']
        if set(c) != {'type', 'subject', 'predicate', 'content'}: raise PermissionError('Only inferred candidates')
        scope = args.get('scope', 'private')
        prior = self.m.db.execute('SELECT source FROM mm_events WHERE owner=? AND scope=? AND event_key=?', (self.p.name, scope, args['key'])).fetchone()
        import json
        observed = json.loads(prior[0])['observed_at'] if prior else time.time()
        return self.m.ingest(self.p, args['key'], {'kind': 'external', 'ref': args['reference'], 'observed_at': observed}, [{**c, 'status': 'inferred'}], scope=scope)
