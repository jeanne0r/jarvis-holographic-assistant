"""Targeted administrator wrapper tests: no sudo/service/GPU/provider operation."""
import ast
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

PATH=Path(__file__).resolve().parents[2]/'ops/pilot-network/run-worker-window.py'
spec=importlib.util.spec_from_file_location('worker_window_admin',PATH)
w=importlib.util.module_from_spec(spec);spec.loader.exec_module(w)


class WorkerWindowAdminTests(unittest.TestCase):
    def test_startup_gate_permissions_under_private_umask(self):
        import os
        import stat
        coordinator=PATH.with_name('install-system-pilot.py')
        tree=ast.parse(coordinator.read_text())
        function=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='supervised_start')
        # Exercise the actual directory-creation statements, with no services.
        calls=[n for n in ast.walk(function) if isinstance(n,ast.Expr)
               and isinstance(n.value,ast.Call) and isinstance(n.value.func,ast.Attribute)
               and isinstance(n.value.func.value,ast.Name) and n.value.func.value.id=='GATE'
               and n.value.func.attr in ('mkdir','chmod')]
        self.assertEqual(['mkdir','chmod'],[n.value.func.attr for n in calls])
        with tempfile.TemporaryDirectory() as directory:
            gate=Path(directory)/'gate'
            old=os.umask(0o077)
            try:
                exec(compile(ast.fix_missing_locations(ast.Module(body=calls,type_ignores=[])),
                             '<actual-gate-creation>','exec'),{'GATE':gate})
            finally:os.umask(old)
            self.assertEqual(0o755,stat.S_IMODE(gate.stat().st_mode))
            secret=Path(directory)/'secret'
            old=os.umask(0o077)
            try:secret.write_text('synthetic')
            finally:os.umask(old)
            self.assertEqual(0o600,stat.S_IMODE(secret.stat().st_mode))

    def test_approval_readable_complete_and_no_overwrite_under_private_umask(self):
        import os
        import stat
        coordinator=PATH.with_name('install-system-pilot.py')
        spec=importlib.util.spec_from_file_location('tested_coordinator',coordinator)
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        payload={'nonce':'synthetic-nonce','session':'synthetic-session','expires':123}
        link=os.link
        with tempfile.TemporaryDirectory() as directory:
            folder=Path(directory)
            def inspect_publication(source,dest,**kwargs):
                # Actual publication sees a complete JSON file with final mode.
                self.assertFalse(dest.exists())
                self.assertEqual(payload,json.loads(source.read_text()))
                self.assertEqual(0o644,stat.S_IMODE(source.stat().st_mode))
                return link(source,dest,**kwargs)
            old=os.umask(0o077)
            try:
                with patch.object(module.os,'link',side_effect=inspect_publication):
                    module.publish_approval(folder,payload)
                self.assertEqual(payload,json.loads((folder/'approved.json').read_text()))
                with self.assertRaises(FileExistsError):
                    module.publish_approval(folder,{'nonce':'replacement'})
            finally:os.umask(old)
            self.assertEqual(payload,json.loads((folder/'approved.json').read_text()))
            self.assertEqual(['approved.json'],[p.name for p in folder.iterdir()])

    def test_approval_publication_failure_cleans_staging(self):
        coordinator=PATH.with_name('install-system-pilot.py')
        spec=importlib.util.spec_from_file_location('tested_coordinator_failure',coordinator)
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as directory:
            folder=Path(directory)
            with patch.object(module.os,'link',side_effect=PermissionError):
                with self.assertRaises(PermissionError):module.publish_approval(folder,{'nonce':'synthetic'})
            self.assertEqual([],list(folder.iterdir()))

    def test_recovery_accepts_only_reviewed_failure_receipt(self):
        parent=Path('/var/backups/jarvis-hermes')
        ident='20261115T195459Z-a89456c1'
        receipt={'window_id':ident,'backup':str(parent/('worker-'+ident))}
        self.assertEqual((ident,parent/('worker-'+ident)),w.validate_failed_window_receipt(receipt,parent))
        for value in ({**receipt,'window_id':'another'}, {**receipt,'backup':'/tmp/other'},
                      {**receipt,'extra':True},{}):
            with self.assertRaises(PermissionError):w.validate_failed_window_receipt(value,parent)

    def test_recovery_nonroot_refused_before_any_activity(self):
        with patch('sys.argv',[str(PATH),'--approved-recovery-window']), \
             patch.object(w.os,'geteuid',return_value=1000),patch.object(w,'load') as load:
            with self.assertRaises(PermissionError):w.main()
            load.assert_not_called()

    def cfg(self):
        return {'operations':dict.fromkeys(['admissionEnabled','textEnabled','workerEnabled','voiceEnabled'],False),
                'bridgeToken':'b'*40}

    def tokens(self):return dict(zip(w.NAMES,['h'*40,'m'*40,'r'*40]))

    def test_window_bound_and_narrow_admission(self):
        original=self.cfg()
        cfg,window=w.runtime_config(original,self.tokens(),'s'*40,now=1000)
        self.assertEqual(1300,window['expires_at'])
        self.assertEqual({'calls':6,'missions':1},window['limits'])
        self.assertEqual(98304,window['local_token_limit'])
        self.assertFalse(window['closed'])
        self.assertEqual(1300,cfg['operations']['runtime']['expiresAt'])
        self.assertEqual(1,cfg['operations']['runtime']['maxMissions'])
        self.assertFalse(cfg['operations']['textEnabled'])
        self.assertFalse(cfg['operations']['voiceEnabled'])
        self.assertTrue(cfg['operations']['workerEnabled'])
        self.assertTrue(cfg['operations']['admissionEnabled'])
        self.assertEqual(self.cfg(),original)

    def test_identity_and_original_profile_rejections(self):
        cases=[(self.cfg(),{**self.tokens(),'hermes.token':'short'},'s'*40),
               (self.cfg(),{**self.tokens(),'hermes.token':'m'*40},'s'*40),
               (self.cfg(),self.tokens(),'b'*40),
               ({**self.cfg(),'operations':{}},self.tokens(),'s'*40)]
        for cfg,tokens,sup in cases:
            with self.subTest(cfg=cfg):
                with self.assertRaises(PermissionError):w.runtime_config(cfg,tokens,sup,now=1000)

    def test_legacy_token_endings_match_existing_loader_without_file_change(self):
        from memory_manager.phase4.credentials import load_token
        with tempfile.TemporaryDirectory() as directory:
            p=Path(directory)/'fixture.token'
            for ending in ['', '\n', '\r\n']:
                raw=('h'*64+ending).encode()
                p.write_bytes(raw);p.chmod(0o600)
                self.assertEqual(load_token(p),w.credential_value(p.read_text()))
                self.assertEqual(raw,p.read_bytes())
            for raw in ['h'*16, 'h'*30+'\n'+'h'*33, 'h'*30+' '+'h'*33]:
                with self.assertRaises(PermissionError):w.credential_value(raw)

    def test_collisions_are_checked_after_loading_not_on_file_encoding(self):
        values=self.tokens()
        values['hermes.token']=w.credential_value('h'*64+'\n')
        values['model.token']=w.credential_value('h'*64+'\r\n')
        with self.assertRaises(PermissionError):w.runtime_config(self.cfg(),values,'s'*40,now=1000)

    def test_fingerprint_refuses_unknown_bytes_and_symlink(self):
        with tempfile.TemporaryDirectory() as directory:
            p=Path(directory)/'fixture';p.write_bytes(b'fixture')
            self.assertEqual(b'fixture',w.read_verified(p,w.hashlib.sha256(b'fixture').hexdigest()))
            with self.assertRaises(PermissionError):w.read_verified(p,'0'*64)
            link=Path(directory)/'link';link.symlink_to(p)
            with self.assertRaises(PermissionError):w.read_verified(link,w.hashlib.sha256(b'fixture').hexdigest())

    def test_nonroot_does_not_touch_services_or_paths(self):
        with patch('sys.argv',[str(PATH),'--approved-first-window']), \
             patch.object(w.os,'geteuid',return_value=1000),patch.object(w,'load') as load:
            with self.assertRaises(PermissionError):w.main()
            load.assert_not_called()

    def test_network_check_failure_does_not_become_success(self):
        with self.assertRaises(PermissionError):
            w.child_check("raise PermissionError('fixture')",runner=lambda *args:list(args),timeout=3)

    def test_private_input_is_read_and_temporary_output_does_not_wait_for_descendant_eof(self):
        import time
        code="import json,sys,subprocess;v=json.load(sys.stdin);subprocess.Popen([sys.executable,'-c','import time;time.sleep(10)']);print(json.dumps({'passed':v=={'fixture':True}}),flush=True)"
        start=time.monotonic()
        w.child_check(code,input=json.dumps({'fixture':True}),runner=lambda *args:list(args),timeout=3)
        self.assertLess(time.monotonic()-start,3)

    def test_timeout_still_fails_closed_and_progress_cannot_print_private_fields(self):
        with self.assertRaises(w.subprocess.TimeoutExpired):
            w.child_check('import time;time.sleep(10)',runner=lambda *args:list(args),timeout=.2)
        self.assertIsNone(w.public_progress('{"secret":"fixture"}'))
        self.assertEqual({'event':'source-batch-verified','files':2500},
            w.public_progress('{"event":"source-batch-verified","files":2500,"secret":"fixture"}'))
        self.assertIsNone(w.public_progress('{"event":"preflight-check","stage":"fixture-secret"}'))

    def test_windows_diagnostic_returns_before_backup_and_arming(self):
        tree=ast.parse(PATH.read_text())
        main=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='main')
        branch=next(n for n in main.body if isinstance(n,ast.If) and
                    isinstance(n.test,ast.Attribute) and n.test.attr=='diagnose_windows')
        self.assertIsInstance(branch.body[-1],ast.Return)
        first_write=min(n.lineno for n in ast.walk(main) if isinstance(n,ast.Call) and
                        isinstance(n.func,ast.Attribute) and n.func.attr in
                        {'replace_private','private_report','snapshot','mkdir'})
        self.assertLess(branch.end_lineno,first_write)

    def test_no_mission_post_gateway_restart_or_windows_install_path(self):
        tree=ast.parse(PATH.read_text())
        # HTTP clients in this wrapper must only GET. Existing native runtime
        # admission is owned by the installed controller and the human click.
        verbs=[]
        for node in ast.walk(tree):
            if isinstance(node,ast.Call) and node.args and isinstance(node.args[0],ast.Constant):
                value=node.args[0].value
                if value in ('GET','POST','DELETE','PUT','PATCH'):verbs.append(value)
        self.assertTrue(verbs)
        self.assertEqual({'GET'},set(verbs))
        source=PATH.read_text()
        self.assertNotIn("user_command('restart'",source)
        self.assertNotIn('SO_REUSEADDR',source)
        self.assertNotIn('pip install',source)
        self.assertNotIn('ollama pull',source)
        self.assertIn('os.O_EXCL',source)

    def test_pinned_administrator_sources_and_manifests_match(self):
        for name,value in [('ops/pilot-network/install-operational-panel.py',w.INSTALLER_SHA),
                           ('ops/pilot-network/install-system-pilot.py',w.COORDINATOR_SHA),
                           ('ops/pilot-network/deploy-private-embedded.py',w.HELPER_SHA),
                           ('memory_manager/phase4/credentials.py',w.CREDENTIALS_SHA),
                           ('docs/HERMES_OPERATIONAL_MANIFEST.json',w.BASE_SHA),
                           ('docs/HERMES_OPERATIONAL_RECONCILED_MANIFEST.json',w.EFFECTIVE_SHA)]:
            w.read_verified(w.SRC/name,value)

    def test_diagnostic_returns_before_windows_checks_or_mutations(self):
        tree=ast.parse(PATH.read_text())
        main=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='main')
        branch=next(n for n in main.body if isinstance(n,ast.If) and
                    isinstance(n.test,ast.Attribute) and n.test.attr=='diagnose_only')
        self.assertIsInstance(branch.body[-1],ast.Return)
        first_child_check=min(n.lineno for n in ast.walk(main) if isinstance(n,ast.Call) and
                              isinstance(n.func,ast.Name) and n.func.id=='child_check')
        first_write=min(n.lineno for n in ast.walk(main) if isinstance(n,ast.Call) and
                        isinstance(n.func,ast.Attribute) and n.func.attr in
                        {'replace_private','private_report','snapshot','mkdir'})
        self.assertLess(branch.end_lineno,first_child_check)
        self.assertLess(branch.end_lineno,first_write)


if __name__=='__main__':unittest.main()
