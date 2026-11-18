"""Accord-3 preparation tests, without accounts, services, SSH or GPU calls."""
import importlib.util,json,os,tempfile,unittest,socket,subprocess,sys,shutil
from pathlib import Path
from unittest.mock import patch
from types import SimpleNamespace

FILE=Path(__file__).resolve().parents[2]/'ops/demand/commission.py'
spec=importlib.util.spec_from_file_location('commission',FILE)
c=importlib.util.module_from_spec(spec);spec.loader.exec_module(c)

class CommissionTests(unittest.TestCase):
    def cfg(self):
        return {'syntheticOnly':True,'dispatchEnabled':False,'bridgeToken':'b'*48,
                'operations':{'admissionEnabled':True,'textEnabled':True,'workerEnabled':False,'voiceEnabled':False},
                'missionLimits':{'calls':6,'tokens':98304,'seconds':240,'attempts':1,'remoteCostChf':0},
                'humanHash':'h'*64,'onDemand':{'commissioned':True,'accepting':True,'executionEnabled':False,'schedulerToken':'s'*48,'runtime':None}}
    def test_exact_execution_grants_preserve_existing_human_queue_and_voice(self):
        original=self.cfg();before=json.dumps(original,sort_keys=True)
        tokens={n:n[0]*48 for n in ['hermes.token','model.token','memory.token']}
        # model and memory share an initial: distinct tokens are mandatory.
        with self.assertRaises(PermissionError):c.execution_profile(original,tokens,'o'*48)
        tokens['memory.token']='r'*48
        armed=c.execution_profile(original,tokens,'o'*48)
        self.assertTrue(armed['onDemand']['executionEnabled']);self.assertFalse(armed['operations']['workerEnabled'])
        self.assertFalse(armed['operations']['voiceEnabled']);self.assertEqual(armed['humanHash'],original['humanHash'])
        self.assertEqual(armed['onDemand']['schedulerToken'],original['onDemand']['schedulerToken'])
        self.assertEqual(json.dumps(original,sort_keys=True),before)
    def test_paid_budget_altered_permissions_and_uncommissioned_profile_denied(self):
        tokens={'hermes.token':'h'*48,'model.token':'m'*48,'memory.token':'r'*48}
        for change in [lambda v:v.update(syntheticOnly=False),lambda v:v['operations'].update(workerEnabled=True),
                       lambda v:v['operations'].update(voiceEnabled=True),lambda v:v['missionLimits'].update(remoteCostChf=1),
                       lambda v:v['onDemand'].update(executionEnabled=True),lambda v:v['onDemand'].update(commissioned=False)]:
            cfg=self.cfg();change(cfg)
            with self.assertRaises(PermissionError):c.execution_profile(cfg,tokens,'o'*48)
    def rows(self):
        return [{'path':n,'before':'b'*64,'after':'a'*64} for n in ['memory_manager/phase2/mcp.py','memory_manager/phase2/memory_tools.py','memory_manager/phase3/mcp.py']]
    def test_windows_targets_are_only_reviewed_three_files(self):
        self.assertEqual(len(c.windows_paths(self.rows())),3)
        for bad in [self.rows()+[self.rows()[0]],self.rows()[:2],self.rows()[:2]+[{'path':'../../personal'}]]:
            with self.assertRaises(PermissionError):c.windows_paths(bad)
    def test_windows_preimage_or_existing_runtime_refuses_before_writes(self):
        for inventory in [{'idle':False,'hashes':{}},{'idle':True,'hashes':{}}]:
            with patch.object(c,'windows_inventory',return_value=inventory),patch.object(c,'remote') as remote,patch.object(c,'write') as write:
                with self.assertRaises(PermissionError):c.patch_windows(self.rows(),{},'fixed-test')
                remote.assert_not_called();write.assert_not_called()
    def test_all_windows_backups_precede_any_source_transfer(self):
        rows=self.rows();paths=c.windows_paths(rows);inventory={'idle':True,'hashes':{p:'b'*64 for p in paths.values()}}
        actions=[]
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'data').mkdir();(root/'backup').mkdir()
            def write(path,raw,*args,**kwargs):path.write_bytes(raw)
            def remote(script):actions.append(('remote',script));return {'verified':True}
            def command(args,**kwargs):actions.append(('transfer',args));return b''
            with patch.object(c,'SRC',root),patch.object(c,'BACKUP',root/'backup'),patch.object(c,'windows_inventory',return_value=inventory),patch.object(c,'write',side_effect=write),patch.object(c,'remote',side_effect=remote),patch.object(c,'command',side_effect=command),patch.object(c.pwd,'getpwnam',return_value=SimpleNamespace(pw_uid=os.getuid(),pw_gid=os.getgid())):
                folder=c.patch_windows(rows,{'supervisor/'+r['path']:b'code' for r in rows},'synthetic-test')
            self.assertIn('JarvisHermesLab',folder)
            self.assertEqual(actions[0][0],'remote');self.assertEqual(actions[0][1].count('Copy-Item'),3)
            self.assertEqual(sum(a[0]=='transfer' for a in actions),3)
            for kind,body in actions:
                if kind=='remote' and '[IO.File]::Replace' in body:self.assertIn('.sddl',body);self.assertIn('Concurrent source drift',body)
            self.assertEqual(list((root/'data').iterdir()),[])
    def test_network_rule_digest_ignores_only_kernel_metadata(self):
        a={'nftables':[{'metainfo':{'version':'x'}},{'rule':{'handle':4,'expr':[{'match':{'right':8797}},{'counter':{'packets':0,'bytes':0}}]}}]}
        b=json.loads(json.dumps(a));b['nftables'][1]['rule']['handle']=19;b['nftables'][1]['rule']['expr'][1]['counter']['packets']=5
        self.assertEqual(c.normalized(a),c.normalized(b));b['nftables'][1]['rule']['expr'][0]['match']['right']=8787
        self.assertNotEqual(c.normalized(a),c.normalized(b))
    def test_no_administrator_means_no_operations(self):
        with patch.object(c.os,'geteuid',return_value=1000),patch.object(c.sys,'argv',['commission','--accord-3-approved']),patch.object(c,'command') as command:
            with self.assertRaises(PermissionError):c.main()
            command.assert_not_called()
    def test_busy_local_forward_is_deferred_before_reservation(self):
        from scripts.demand_supervisor import local_ports_available
        with socket.socket() as listener:
            listener.bind(('127.0.0.1',0));listener.listen();port=listener.getsockname()[1]
            self.assertFalse(local_ports_available((port,)))
            self.assertEqual(listener.getsockopt(socket.SOL_SOCKET,socket.SO_ACCEPTCONN),1)
        self.assertTrue(local_ports_available((port,)))
    def test_identity_input_is_read_before_ssh_can_consume_stdin(self):
        with tempfile.TemporaryDirectory() as tmp:
            package=Path(tmp)/'scripts';package.mkdir();(package/'__init__.py').write_text('')
            (package/'audit_gpu.py').write_text("import sys\ndef collect():\n sys.stdin.read() # Simulate a subprocess inheriting and consuming stdin.\n return {'available':True}\n")
            (package/'demand_supervisor.py').write_text("def runtime_identity_check(expected):\n if expected!={'hermes.token':'verified-digest'}:raise PermissionError('Identity mismatch')\n")
            result=subprocess.run([sys.executable,'-B','-c',c.WINDOWS_READONLY_PREFLIGHT],input=b'{"hermes.token":"verified-digest"}',capture_output=True,cwd=tmp,timeout=5)
            self.assertEqual(result.returncode,0,result.stderr.decode());self.assertEqual(json.loads(result.stdout),{'available':True})
    def test_code_directory_access_survives_restrictive_umask_without_exposing_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'code';state=Path(tmp)/'private-state'
            mask=os.umask(0o077)
            try:
                root.mkdir(mode=0o755);nested=root/'package';nested.mkdir(mode=0o755)
                code=nested/'module.py';code.write_text('pass');code.chmod(0o644)
                state.mkdir(mode=0o700);secret=state/'identity';secret.write_bytes(b'private')
            finally:os.umask(mask)
            self.assertEqual(root.stat().st_mode&0o777,0o700)
            c.code_directory_policy(root,os.getgid(),apply=True,owner_uid=os.getuid())
            self.assertEqual(root.stat().st_mode&0o777,0o750);self.assertEqual(nested.stat().st_mode&0o777,0o750)
            self.assertEqual(code.stat().st_mode&0o777,0o644)
            self.assertEqual(state.stat().st_mode&0o777,0o700);self.assertEqual(secret.stat().st_mode&0o777,0o600)
    def test_code_policy_rejects_links_and_writable_content_before_any_chmod(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'code';root.mkdir(mode=0o700);file=root/'module.py';file.write_bytes(b'code');file.chmod(0o664)
            with self.assertRaises(PermissionError):c.code_directory_policy(root,os.getgid(),apply=True,owner_uid=os.getuid())
            self.assertEqual(root.stat().st_mode&0o777,0o700)
            file.chmod(0o644);(root/'link').symlink_to(Path(tmp))
            with self.assertRaises(PermissionError):c.code_directory_policy(root,os.getgid(),apply=True,owner_uid=os.getuid())
            self.assertEqual(root.stat().st_mode&0o777,0o700)
    def test_code_policy_does_not_adopt_foreign_owned_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(PermissionError):c.code_directory_policy(Path(tmp),os.getgid(),apply=True,owner_uid=os.getuid()+1)
    def test_access_probe_launches_from_installed_code_not_private_workspace(self):
        reply=SimpleNamespace(returncode=0,stdout=b'{"passed":true,"stage":"complete"}',stderr=b'')
        with patch.object(c.subprocess,'run',return_value=reply) as run:
            self.assertTrue(c.application_access_probe(c.ROOT)['passed'])
            self.assertEqual(run.call_args.kwargs['cwd'],c.ROOT)
            self.assertNotEqual(run.call_args.kwargs['cwd'],c.SRC)
    def test_access_diagnostic_does_not_export_child_traceback_or_unexpected_fields(self):
        replies=[b'',b'{"passed":false,"stage":"imports","token":"private-fixture"}']
        for output in replies:
            reply=SimpleNamespace(returncode=1,stdout=output,stderr=b'private-fixture')
            with patch.object(c.subprocess,'run',return_value=reply):
                result=c.application_access_probe(c.ROOT)
                self.assertFalse(result['passed']);self.assertNotIn('private-fixture',json.dumps(result))
    def test_real_packaged_import_probe_with_private_fixture_configs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'code';shutil.copytree(c.PACKAGE/'supervisor',root)
            config=Path(tmp)/'config.json';identity=Path(tmp)/'identity.json';bindings=Path(tmp)/'bindings.json'
            for path,value in [(config,{'identityFile':str(identity),'bindingsFile':str(bindings)}),(identity,{}),(bindings,{})]:
                path.write_text(json.dumps(value));path.chmod(0o600)
            result=subprocess.run([sys.executable,'-B','-c',c.application_access_code(root,config)],capture_output=True,cwd=root,env={'PATH':'/usr/bin:/bin','HOME':tmp,'PYTHONDONTWRITEBYTECODE':'1'},timeout=10)
            self.assertEqual(result.returncode,0,result.stderr.decode());self.assertEqual(json.loads(result.stdout),{'passed':True,'stage':'complete'})
            config.chmod(0o644)
            result=subprocess.run([sys.executable,'-B','-c',c.application_access_code(root,config)],capture_output=True,cwd=root,env={'PATH':'/usr/bin:/bin','HOME':tmp,'PYTHONDONTWRITEBYTECODE':'1'},timeout=10)
            diagnostic=json.loads(result.stdout)
            self.assertNotEqual(result.returncode,0);self.assertEqual(diagnostic['stage'],'configuration');self.assertEqual(diagnostic['error_type'],'PermissionError')
    def test_real_generated_source_manifest_fits_only_explicit_config_bound(self):
        from scripts.demand_supervisor import private_json,CONFIG_MAX_BYTES
        package=c.PACKAGE/'supervisor'
        bindings={str(p.relative_to(package)):'a'*64 for p in package.rglob('*') if p.is_file() and p.suffix in {'.py','.mjs','.cjs'}}
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'config.json';value={'sourceFiles':bindings};path.write_text(json.dumps(value));path.chmod(0o600)
            self.assertGreater(path.stat().st_size,16384)
            with self.assertRaises(PermissionError):private_json(path)
            self.assertEqual(private_json(path,max_bytes=CONFIG_MAX_BYTES),value)
            path.chmod(0o644)
            with self.assertRaises(PermissionError):private_json(path,max_bytes=CONFIG_MAX_BYTES)
            path.chmod(0o600);link=Path(tmp)/'link.json';link.symlink_to(path)
            with self.assertRaises(PermissionError):private_json(link,max_bytes=CONFIG_MAX_BYTES)
            path.write_text(json.dumps({'too_large':'x'*(CONFIG_MAX_BYTES+1)}))
            with self.assertRaises(PermissionError):private_json(path,max_bytes=CONFIG_MAX_BYTES)
            for bound in [0,CONFIG_MAX_BYTES+1,True]:
                with self.assertRaises(ValueError):private_json(path,max_bytes=bound)
    def test_reader_repair_only_changes_its_own_source_hash(self):
        cfg={**self.cfg(),'sourceFiles':{'scripts/demand_supervisor.py':c.PREVIOUS_EXECUTOR_SHA,'memory_manager/store.py':'b'*64}}
        before=json.dumps(cfg,sort_keys=True);updated=c.updated_reader_config(cfg)
        self.assertEqual(json.dumps(cfg,sort_keys=True),before)
        self.assertEqual(updated['sourceFiles']['scripts/demand_supervisor.py'],c.EXECUTOR_SHA)
        self.assertEqual(updated['sourceFiles']['memory_manager/store.py'],'b'*64)
        self.assertEqual({k:v for k,v in updated.items() if k!='sourceFiles'},{k:v for k,v in cfg.items() if k!='sourceFiles'})
        with self.assertRaises(PermissionError):c.updated_reader_config({**cfg,'sourceFiles':{'scripts/demand_supervisor.py':'unexplained'}})
    def test_updated_packaged_access_probe_reads_large_config_without_service_or_gpu(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'code';shutil.copytree(c.PACKAGE/'supervisor',root)
            (root/'scripts/demand_supervisor.py').write_bytes((c.SRC/'scripts/demand_supervisor.py').read_bytes())
            config=Path(tmp)/'config.json';identity=Path(tmp)/'identity.json';bindings=Path(tmp)/'bindings.json'
            hashes={str(p.relative_to(root)):'a'*64 for p in root.rglob('*.py')}
            value={'identityFile':str(identity),'bindingsFile':str(bindings),'sourceFiles':hashes}
            for path,data in [(config,value),(identity,{}),(bindings,{})]:path.write_text(json.dumps(data));path.chmod(0o600)
            self.assertGreater(config.stat().st_size,16384)
            result=subprocess.run([sys.executable,'-B','-c',c.application_access_code(root,config)],capture_output=True,cwd=root,env={'PATH':'/usr/bin:/bin','HOME':tmp,'PYTHONDONTWRITEBYTECODE':'1'},timeout=10)
            self.assertEqual(result.returncode,0,result.stderr.decode());self.assertEqual(json.loads(result.stdout),{'passed':True,'stage':'complete'})

if __name__=='__main__':unittest.main()
