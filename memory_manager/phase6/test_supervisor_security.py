import json,hashlib,stat,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from scripts.demand_supervisor import runtime_identity_check

class SupervisorSecurity(unittest.TestCase):
 # Root receipt (verify_confinement) removed: replaced by the live egress self-test,
 # covered in memory_manager/phase6/test_demand_simple.py.
 def test_windows_digest_and_loader_guards_do_not_print_secrets(self):
    expected={n:hashlib.sha256(n.encode()).hexdigest() for n in ['hermes.token','model.token','memory.token']}
    good=lambda script,**kw:SimpleNamespace(returncode=0,stdout=json.dumps(expected).encode())
    loader=lambda script:{'sha':'56a87075e51c7aa2074c4c70ba7367dca33bbdee5639e55a72dc9d333584c684'}
    self.assertTrue(runtime_identity_check(expected,ssh=good,probe=loader))
    for args in [dict(ssh=lambda *a,**k:SimpleNamespace(returncode=1,stdout=b''),probe=loader),dict(ssh=good,probe=lambda s:{'sha':'0'*64})]:
     with self.assertRaises(PermissionError):runtime_identity_check(expected,**args)

 def test_cleanup_requires_both_owned_jobs_tunnel_and_fresh_listener_check(self):
    from scripts.demand_supervisor import cleanup_verified
    report={'native_windows':{'owned_runtime_cleanup':True,'owned_tunnel_closed':True},'cleanup':{'listener_after':{'listening':False},'supervisor':{'owned_process_stopped_after_close':True}}}
    self.assertTrue(cleanup_verified(report,True));self.assertFalse(cleanup_verified(report,False))
    report['native_windows']['owned_runtime_cleanup']=False
    self.assertFalse(cleanup_verified(report,True))
    self.assertFalse(cleanup_verified({'cleanup':report['cleanup']},True))

 def test_network_probe_requires_negative_witness_and_effective_hooks(self):
    import importlib.util
    path=Path(__file__).resolve().parents[2]/'ops/demand/attest-confinement.py'
    spec=importlib.util.spec_from_file_location('root_probe_contract',path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    observed={'loopback':{'connected':True},'non_loopback':{'connected':False}}
    hooks=['cgroup_inet_ingress','cgroup_inet_egress']
    self.assertTrue(m.verdict(observed,hooks,True,True,False))
    for args in [(observed,[],True,True,False),(observed,hooks,False,True,False),(observed,hooks,True,True,True)]:self.assertFalse(m.verdict(*args))
