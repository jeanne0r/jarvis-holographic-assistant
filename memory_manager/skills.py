"""Small declarative skill experiment: no execution of agent-provided code.

Evaluation is recomputed at publication, so a claimed pass or modified report
cannot authorize a version. Publication returns a manifest for Git review only.
"""
from .store import digest

CASES = [
    ([1, 1, 1, 1], {'count': 4, 'identical': True, 'capacity_kg': 1}),
    ([1, 2, 5, 10], {'count': 4, 'identical': False, 'capacity_kg': None}),
    ([2, 2], {'count': 2, 'identical': True, 'capacity_kg': 2}),
]


def apply(spec, values):
    if set(spec) != {'name', 'version', 'strategy'} or spec['name'] != 'compare-load-cells':
        raise ValueError('Unknown experimental skill')
    if not values or len(values) > 100 or any(type(v) not in (int, float) or not 0 < v <= 10000 for v in values):
        raise ValueError('Bounded positive capacities required')
    if spec['strategy'] == 'assume-identical':
        same = True  # Historical synthetic failure, preserved for evaluation.
    elif spec['strategy'] == 'compare-all':
        same = all(v == values[0] for v in values)
    else:
        raise ValueError('Strategy denied')
    return {'count': len(values), 'identical': same, 'capacity_kg': values[0] if same else None}


def evaluate(spec):
    results = [apply(spec, values) == expected for values, expected in CASES]
    return {'spec_hash': digest(spec), 'suite_hash': digest(CASES), 'passed': all(results),
            'cases_passed': sum(results), 'cases_total': len(results)}


def publication_manifest(principal, spec, baseline):
    principal.require('reviewer')
    report, old = evaluate(spec), evaluate(baseline)
    old_results = [apply(baseline, values) == expected for values, expected in CASES]
    new_results = [apply(spec, values) == expected for values, expected in CASES]
    if not report['passed'] or any(prior and not after for prior, after in zip(old_results, new_results)):
        raise ValueError('Tests or non-regression gate failed')
    if type(spec['version']) is not int or spec['version'] <= baseline['version']:
        raise ValueError('Monotonic skill version required')
    return {'status': 'reviewed_for_git', 'reviewer': principal.name, 'evaluation': report,
            'baseline': old, 'skill': spec, 'installed': False}
