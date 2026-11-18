"""Synthetic real-model consolidation trial, reusing phase-two checkpoints."""
import json
from pathlib import Path

from ..store import Memory, Principal
from ..phase2 import budgets, database
from ..phase2.pipeline import Pipeline
from .lab import HOST, ROOT, seed


def run(model, destination):
    folder = Path(destination).resolve()
    if not folder.is_relative_to(ROOT / 'data/phase3'):
        raise ValueError('Laboratory data only')
    folder.mkdir(mode=0o700, parents=True, exist_ok=False)
    path = folder / 'memory.sqlite'
    principal = Principal(HOST.name, HOST.scopes,
        HOST.roles | {'consolidator', 'budget_admin', 'metered_caller'}, 'pipeline-host')
    memory = Memory(path, create=True)
    try:
        database.migrate(memory)
        ids = seed(memory)
        bid = budgets.create(memory, principal, token_limit=model.config.context_tokens)
        pipeline = Pipeline(memory, principal, budget_id=bid)
        events = [{'id': 'e1', 'text': 'DoseLab possède quatre cellules identiques de 1 kg.',
                   'ref': 'synthetic://phase3/local-event', 'observed_at': 1700000300}]
        jid = pipeline.enqueue('gpu-local-consolidation', events, max_attempts=1,
                               max_tokens=model.config.context_tokens, seconds=120)
        interrupted = False
        try:
            pipeline.run(jid, model, interrupt_after_checkpoint=True)
        except InterruptedError:
            interrupted = True
        row = pipeline.get(jid)
        if not interrupted:
            return {'passed': False, 'state': row['state'], 'model_checkpoint_reached': False,
                    'note': 'No memory success claimed; the real extraction did not reach a durable proposal.'}
    finally:
        memory.close()

    class NoSecondInference:
        config = model.config
        def generate(self, *_args, **_kwargs):
            raise AssertionError('A checkpoint replay must not call the model twice')

    memory = Memory(path)
    try:
        pipeline = Pipeline(memory, principal, budget_id=bid)
        resumed = pipeline.run(jid, NoSecondInference())
        count = memory.db.execute('SELECT count(*) FROM mm_revisions').fetchone()[0]
        pipeline.run(jid, NoSecondInference())
        same = count == memory.db.execute('SELECT count(*) FROM mm_revisions').fetchone()[0]
        report = json.loads(resumed['result'])
        history = memory.history(principal, ids['configuration_memory_id'])
        new_rows = [r for r in memory.current(principal) if r['source']['kind'] == 'model']
        checks = {'job_completed': resumed['state'] == 'completed', 'resumed_after_reopen': True,
                  'nonempty_candidates': bool(report['candidates']), 'idempotent_replay': same,
                  'only_inferred': bool(new_rows) and all(r['status'] == 'inferred' for r in new_rows),
                  'old_configuration_superseded': history[0]['effective_status'] == 'superseded',
                  'current_configuration_preserved': history[-1]['content']['capacities_kg'] == [1, 1, 1, 1],
                  'one_metered_call': memory.db.execute('SELECT count(*) FROM p2_usage').fetchone()[0] == 1}
        return {'passed': all(checks.values()), 'checks': checks, 'job_id': jid,
                'extraction': report, 'metrics': json.loads(resumed['metrics']),
                'memory_ids': [r['memory_id'] for r in new_rows],
                'provenance': [r['source'] for r in new_rows], 'hermes_runtime_tested': False}
    finally:
        memory.close()
