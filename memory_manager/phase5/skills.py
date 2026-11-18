"""Host-controlled extended evaluation and preparation only; no publish operation."""
from ..store import digest
from ..phase2 import skill_registry as registry

# Expected results are independent of the proposal. Context is supplied by the
# host, never accepted from a model's assertion that sources are current.
CASES = [
    ({'flow_lpm':7,'fresh':True}, {}, 'report_only'),
    ({}, {}, 'request_human_review'),
    ({'fresh':True}, {}, 'request_human_review'),
    ({'flow_lpm':7}, {}, 'request_human_review'),
    ({'flow_lpm':True,'fresh':True}, {}, 'request_human_review'),
    ({'flow_lpm':-1,'fresh':True}, {}, 'request_human_review'),
    ({'flow_lpm':5.99,'fresh':True}, {}, 'request_human_review'),
    ({'flow_lpm':6,'fresh':True}, {}, 'report_only'),
    ({'flow_lpm':7,'fresh':'true'}, {}, 'request_human_review'),
    ({'flow_lpm':7,'fresh':False}, {}, 'request_human_review'),
    ({'flow_lpm':7,'fresh':True}, {'contradiction':True}, 'request_human_review'),
    ({'flow_lpm':7,'fresh':True}, {'superseded':True}, 'request_human_review'),
    ({'flow_lpm':7,'fresh':True}, {'source_accepted':False}, 'request_human_review'),
    ({'flow_lpm':7,'fresh':True}, {'same_procedure':False}, 'request_human_review'),
]


def recommend(spec,sample,*,source_accepted=True,contradiction=False,superseded=False,same_procedure=True):
    registry.check(spec)
    if source_accepted is not True or contradiction is not False or superseded is not False or same_procedure is not True:
        return 'request_human_review'
    return registry.apply(spec,sample)


def evaluate(spec):
    results = [recommend(spec,sample,**context)==expected for sample,context,expected in CASES]
    # Non-finite floats cannot be included in the JSON suite fingerprint.
    results += [recommend(spec,{'flow_lpm':x,'fresh':True})=='request_human_review' for x in (float('nan'),float('inf'))]
    return {'spec_hash':digest(spec),'suite_hash':digest({'cases':CASES,'extra':['nan','infinity']}),
            'results':results,'passed':all(results),'total':len(results),'passed_count':sum(results)}


def prepare_release(memory,principal,name,version):
    principal.require('reviewer')
    value=registry.get(memory,principal,name,version)
    if value['proposed_by']==principal.actor: raise PermissionError('Independent reviewer required')
    if not value['sources_current_accepted']: raise ValueError('Sources no longer current and accepted')
    result=evaluate(value['spec'])
    if not result['passed']: raise ValueError('Extended suite failed')
    manifest={'name':name,'version':version,'fingerprint':value['fingerprint'],
        'sources':value['sources'],'evaluation':result,'state':'prepared_for_review',
        'execution_authorized':False,'publication_authorized':False,
        'runtime':'host-declarative-v1','reviewer':principal.actor}
    return {**manifest,'manifest_sha256':digest(manifest)}
