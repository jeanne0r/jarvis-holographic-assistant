"""Simplified supervisor installation: pure logic, no root, no network beyond loopback."""
import importlib.util, json, os, re, socket, tempfile, unittest, unittest.mock
from pathlib import Path
from scripts import egress_selftest as st

REPO = Path(__file__).resolve().parents[2]
SIMPLE = REPO / 'ops/demand-simple'
spec = importlib.util.spec_from_file_location('simple_install', SIMPLE / 'install.py')
inst = importlib.util.module_from_spec(spec); spec.loader.exec_module(inst)

POLICY = {'queue': ['127.0.0.1', 8797], 'windows': ['198.18.0.96', 22], 'witness_port': 8792,
          'forbidden': [['127.0.0.1', 8788], ['198.18.0.96', 3389]]}


def fake(table, witness_arrives=False):
    """connect() stub keyed by (host, port); witness stub reports delivery."""
    def connect(host, port, family=socket.AF_INET, timeout=1.0):
        return table.get((host, int(port)), 'refused')
    def witness(host, port, c):
        out = 'connected' if witness_arrives else c(host, port)
        return {'target': [host, port], 'outcome': out, 'ok': out != 'connected' and not witness_arrives}
    return connect, witness


GOOD = {('127.0.0.1', 8797): 'connected', ('198.18.0.96', 22): 'connected'}


class EgressSelfTest(unittest.TestCase):
    def check(self, table, mode='start', arrives=False):
        connect, witness = fake(table, arrives)
        return st.run(POLICY, mode=mode, connect=connect, witness=witness, address=lambda _: '192.0.2.165')

    def test_passes_only_when_allowed_and_forbidden_both_hold(self):
        r = self.check(GOOD, 'mission')
        self.assertTrue(r['passed'])
        kinds = {c['kind'] for c in r['checks']}
        self.assertEqual(kinds, {'allowed', 'forbidden'})

    def test_queue_down_refuses_start_positive_control(self):
        self.assertFalse(self.check({**GOOD, ('127.0.0.1', 8797): 'refused'})['passed'])

    def test_witness_reached_means_filter_absent(self):
        self.assertFalse(self.check(GOOD, arrives=True)['passed'])

    def test_named_forbidden_destination_connecting_fails(self):
        for target in [('127.0.0.1', 8788), ('198.18.0.96', 3389)]:
            self.assertFalse(self.check({**GOOD, target: 'connected'})['passed'], target)

    def test_windows_locally_blocked_always_fails(self):
        for outcome in ['refused', 'eperm']:
            for mode in ['start', 'mission']:
                self.assertFalse(self.check({**GOOD, ('198.18.0.96', 22): outcome}, mode)['passed'])

    def test_windows_absent_allows_start_but_never_a_mission(self):
        for outcome in ['timeout', 'unreachable']:
            t = {**GOOD, ('198.18.0.96', 22): outcome}
            self.assertTrue(self.check(t, 'start')['passed'])
            self.assertFalse(self.check(t, 'mission')['passed'])

    def test_ipv6_reachable_fails(self):
        connect, witness = fake(GOOD)
        def c6(host, port, family=socket.AF_INET, timeout=1.0):
            return 'connected' if family == socket.AF_INET6 else connect(host, port)
        self.assertFalse(st.run(POLICY, connect=c6, witness=witness, address=lambda _: '192.0.2.165')['passed'])

    def test_no_independent_lan_address_fails(self):
        connect, witness = fake(GOOD)
        for addr in ['127.0.0.1', '198.18.0.96']:
            self.assertFalse(st.run(POLICY, connect=connect, witness=witness, address=lambda _: addr)['passed'])

    def test_real_witness_detects_missing_filter(self):
        # No nftables for this UID: our own loopback witness IS reached -> not ok.
        r = st.witness_check('127.0.0.1', 0)
        self.assertEqual(r['outcome'], 'connected'); self.assertFalse(r['ok'])

    def test_policy_must_be_root_owned(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'p.json'; p.write_text(json.dumps(POLICY)); p.chmod(0o644)
            with self.assertRaises(PermissionError): st.load_policy(p)

    def test_verify_raises_and_names_failures(self):
        with unittest.mock.patch.object(st, 'load_policy', return_value=POLICY), \
             unittest.mock.patch.object(st, 'run', return_value={'passed': False, 'checks': [{'name': 'witness_lan', 'ok': False}]}):
            with self.assertRaisesRegex(PermissionError, 'witness_lan'): st.verify('x')


class InstallerLogic(unittest.TestCase):
    def test_closure_is_generated_from_code_not_frozen(self):
        files = inst.import_closure(REPO)
        for must in ['scripts/demand_supervisor.py', 'scripts/egress_selftest.py', 'scripts/run_interactive_hermes.py',
                     'memory_manager/__init__.py', 'memory_manager/phase4/windows.py', *inst.EXTRA_FILES]:
            self.assertIn(must, files)
        # Only the private-boot hook from ops/demand/; never the old commissioning tools.
        self.assertEqual([f for f in files if '/test_' in f or f.startswith('ops/demand')], [inst.BOOT_HOOK])

    def test_closure_follows_function_level_and_relative_imports(self):
        with tempfile.TemporaryDirectory() as d:
            r = Path(d); (r / 'scripts').mkdir(); (r / 'memory_manager/sub').mkdir(parents=True)
            (r / 'memory_manager/__init__.py').write_text(''); (r / 'memory_manager/sub/__init__.py').write_text('')
            (r / 'memory_manager/sub/a.py').write_text('from .b import x\n'); (r / 'memory_manager/sub/b.py').write_text('x=1\n')
            (r / 'memory_manager/unused.py').write_text('')
            (r / 'scripts/main.py').write_text('def f():\n from memory_manager.sub import a\n')
            got = inst.import_closure(r, ['scripts/main.py'], extras=[])
            self.assertEqual(got, ['memory_manager/__init__.py', 'memory_manager/sub/__init__.py',
                                   'memory_manager/sub/a.py', 'memory_manager/sub/b.py', 'scripts/main.py'])

    def test_release_alone_imports_every_module_from_itself(self):
        """Dynamic complement to the AST closure: a tree holding ONLY the release
        files must import every host module, and nothing may come from elsewhere."""
        import shutil, subprocess, sys
        files = inst.import_closure(REPO)
        host_only = [f for f in files if f.endswith('.py') and not f.startswith('ops/')]
        mods = [f[:-3].replace('/', '.').removesuffix('.__init__') for f in host_only]
        with tempfile.TemporaryDirectory() as d:
            for f in files:
                (Path(d) / f).parent.mkdir(parents=True, exist_ok=True); shutil.copyfile(REPO / f, Path(d) / f)
            code = ("import sys,importlib,json;sys.path.insert(0,sys.argv[1]);mods=json.loads(sys.argv[2])\n"
                    "for m in mods: importlib.import_module(m)\n"
                    "bad=[m for m,v in sys.modules.items() if m.split('.')[0] in ('scripts','memory_manager') and not all(p.startswith(sys.argv[1]) for p in ([v.__file__] if getattr(v,'__file__',None) else list(getattr(v,'__path__',[])) or ['?']))]\n"
                    "print(json.dumps({'imported':len(mods),'outside':bad}))")
            r = subprocess.run([sys.executable, '-I', '-B', '-c', code, d, json.dumps(mods)], cwd=d,
                               capture_output=True, text=True, timeout=60, env={'PATH': '/usr/bin:/bin'})
            self.assertEqual(r.returncode, 0, r.stderr[-800:])
            out = json.loads(r.stdout)
            self.assertEqual(out['outside'], []); self.assertEqual(out['imported'], len(mods))

    def test_state_dirs_cover_runtime_writes(self):
        self.assertIn('data/phase4', inst.STATE_DIRS)
        for m in inst.BIND_MOUNTS: self.assertIn(m, inst.STATE_DIRS)

    def test_every_opt_path_referenced_by_installed_units_and_release_ships(self):
        """Regression: private-boot (Required by the supervisor unit) runs code from /opt;
        any /opt/jarvis-hermes-supervisor/<path> named by an installed unit or by a
        release file must be in the release (bind mounts excepted)."""
        files = set(inst.import_closure(REPO))
        sources = [REPO / 'ops/demand-simple/jarvis-hermes-supervisor.service.in',
                   REPO / 'ops/demand/jarvis-hermes-private-boot.service.in'] + [REPO / f for f in files]
        refs = {m for p in sources for m in re.findall(r'/opt/jarvis-hermes-supervisor/([\w./-]+\.\w+)', p.read_text(errors='replace'))}
        refs = {r for r in refs if r.split('/')[0] not in inst.BIND_MOUNTS}
        self.assertIn(inst.BOOT_HOOK, refs); self.assertIn(inst.COORDINATOR, refs)
        self.assertEqual(sorted(refs - files), [])

    def test_rules_digest_is_the_boot_hook_algorithm(self):
        """Extract `normalized` from start-private-queue.py itself and compare digests."""
        import ast, hashlib
        tree = ast.parse((REPO / inst.BOOT_HOOK).read_text())
        fn = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == 'normalized')
        ns = {}; exec(compile(ast.Module([fn], []), 'boot-hook-normalized', 'exec'), ns)
        sample = {'nftables': [{'metainfo': {'version': '1.1.3', 'json_schema_version': 1}},
                               {'table': {'family': 'inet', 'name': 'jarvis_hermes_supervisor', 'handle': 7}},
                               {'rule': {'chain': 'output', 'handle': 3, 'expr': [{'counter': {'packets': 9, 'bytes': 99}}, {'reject': None}]}}]}
        theirs = hashlib.sha256(json.dumps(ns['normalized'](sample), sort_keys=True).encode()).hexdigest()
        self.assertEqual(inst.rules_digest(json.dumps(sample)), theirs)
        moved = json.loads(json.dumps(sample)); moved['nftables'][1]['table']['handle'] = 42
        moved['nftables'][2]['rule']['expr'][0]['counter']['packets'] = 1
        self.assertEqual(inst.rules_digest(json.dumps(moved)), theirs)   # runtime fields ignored

    def test_boot_policy_coordinator_pin_is_checked_never_rewritten(self):
        manifest = {inst.COORDINATOR: 'c' * 64}
        self.assertTrue(inst.check_boot({'coordinatorSha256': 'c' * 64}, manifest))
        with self.assertRaisesRegex(PermissionError, 'coordinatorSha256'): inst.check_boot({'coordinatorSha256': 'd' * 64}, manifest)
        with self.assertRaises(PermissionError): inst.check_boot({}, manifest)
        old = {'coordinatorSha256': 'c' * 64, 'egressFileSha256': 'x', 'egressRulesSha256': 'y', 'other': 1}
        new = inst.merged_boot(old, b'rules', 'r' * 64)
        self.assertEqual(new, {**old, 'egressFileSha256': inst.sha(b'rules'), 'egressRulesSha256': 'r' * 64})

    def test_check_mode_writes_nothing(self):
        with tempfile.TemporaryDirectory() as d:
            i = inst.Installer(REPO, inst.Layout(d), windows_host='198.18.0.96', dry=True)
            target = Path(d) / 'f'
            self.assertTrue(i.put(target, b'x', os.getuid(), os.getgid(), 0o600)); self.assertFalse(target.exists())
            i.mkdir(Path(d) / 'sub', os.getuid(), os.getgid(), 0o700); self.assertFalse((Path(d) / 'sub').exists())
            self.assertEqual(i.changed, [str(target), str(Path(d) / 'sub')])

    def test_config_merge_keeps_operator_values_and_never_enables(self):
        old = {'enabled': False, 'remoteCostChf': 0, 'identityFile': '/etc/x/identity.json',
               'confinementReceipt': '/etc/x/confinement.json', 'sourceFiles': {'scripts/demand_supervisor.py': 'e33e8732' + '0' * 56}}
        manifest = {'scripts/demand_supervisor.py': 'a' * 64}
        cfg = inst.merged_config(old, manifest, '/etc/x/egress-policy.json')
        self.assertIs(cfg['enabled'], False)
        self.assertEqual(cfg['identityFile'], old['identityFile'])
        self.assertNotIn('confinementReceipt', cfg)
        self.assertEqual(cfg['sourceFiles'], manifest)   # the stale e33e8732 hash is replaced, not edited by hand
        self.assertIs(inst.merged_config({**old, 'enabled': True}, manifest, 'p')['enabled'], True)

    def test_generated_config_fits_reader_bound(self):
        from scripts.demand_supervisor import CONFIG_MAX_BYTES
        files = inst.import_closure(REPO)
        raw = inst.dumps(inst.merged_config({'enabled': False}, {f: 'a' * 64 for f in files}, '/etc/p'))
        self.assertLess(len(raw), CONFIG_MAX_BYTES)

    def test_bindings_drift_refused_before_swap(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'b.json'
            p.write_text(json.dumps({'host_files': {'memory_manager/phase2/mcp.py': 'a' * 64}}))
            with self.assertRaisesRegex(PermissionError, 'phase2/mcp.py'):
                inst.check_bindings(p, {'memory_manager/phase2/mcp.py': 'b' * 64})
            self.assertTrue(inst.check_bindings(p, {'memory_manager/phase2/mcp.py': 'a' * 64}))
        self.assertFalse(inst.check_bindings(None, {}))
        # The repository's documented bindings predate the MCP citation fix (d14a2d5):
        docs = REPO / 'docs/HERMES_OPERATIONAL_WINDOWS_BINDINGS.json'
        manifest = {f: inst.sha((REPO / f).read_bytes()) for f in inst.import_closure(REPO)}
        with self.assertRaisesRegex(PermissionError, 'phase2/mcp.py'): inst.check_bindings(docs, manifest)

    def test_render_refuses_leftover_placeholders(self):
        t = (SIMPLE / 'supervisor-egress.nft.in').read_text()
        with self.assertRaises(ValueError): inst.render(t, SUPERVISOR_UID=995)
        out = inst.render(t, SUPERVISOR_UID=995, WINDOWS_HOST='192.0.2.96')
        self.assertNotIn('@', ''.join(l for l in out.splitlines() if not l.strip().startswith('#')))

    def test_nft_is_whitelist_without_gateway_and_ends_in_reject(self):
        out = inst.render((SIMPLE / 'supervisor-egress.nft.in').read_text(), SUPERVISOR_UID=995, WINDOWS_HOST='192.0.2.96')
        rules = [l.strip() for l in out.splitlines() if l.strip().startswith('meta skuid')]
        self.assertEqual(rules[-1], 'meta skuid 995 reject')
        accepts = ' '.join(r for r in rules if r.endswith('accept'))
        for port in ['8787', '8788', '8123', '3389', '445']: self.assertNotIn(port, accepts)
        self.assertIn('delete table inet jarvis_hermes_supervisor', out)   # atomic idempotent replace

    def test_policy_forbids_gateway_and_extra_actuator_targets(self):
        p = inst.egress_policy('192.0.2.96', [('192.0.2.50', '8123')])
        self.assertIn(['127.0.0.1', 8788], p['forbidden']); self.assertIn(['192.0.2.50', 8123], p['forbidden'])
        self.assertEqual(p['windows'], ['192.0.2.96', 22])

    def test_unit_keeps_current_hardening_and_only_swaps_network_proof(self):
        old = (REPO / 'ops/demand/jarvis-hermes-supervisor.service.in').read_text().splitlines()
        new = (SIMPLE / 'jarvis-hermes-supervisor.service.in').read_text().splitlines()
        code = lambda lines: {l for l in lines if l and not l.startswith('#')}
        self.assertEqual(code(old) - code(new), {'ExecStartPost=+/usr/bin/systemctl start jarvis-hermes-confinement.service',
                                                 'IPAddressDeny=any', 'IPAddressAllow=127.0.0.0/8 192.0.2.96/32'})
        added = code(new) - code(old)
        self.assertEqual(len(added), 2); self.assertTrue(all(l.startswith('ExecStartPre=') for l in added))
        order = [i for i, l in enumerate(new) if l.startswith(('ExecStartPre=+/usr/sbin/nft', 'ExecStartPre=/usr/bin/python3 -B -m scripts.egress_selftest', 'ExecStart='))]
        self.assertEqual(order, sorted(order)); self.assertEqual(len(order), 3)
        self.assertIn('Restart=no', new); self.assertIn('User=jarvis-hermes-supervisor', new)

    def test_install_order_and_no_implicit_start(self):
        calls = []
        i = inst.Installer(REPO, inst.Layout('/nonexistent'), windows_host='198.18.0.96')
        for name in ['refuse_if_active', 'account', 'directories', 'release', 'config', 'network', 'boot_policy', 'unit']:
            setattr(i, name, (lambda n: lambda: calls.append(n))(name))
        i.verify_as_service = lambda: calls.append('verify') or {}
        i.manifest = {}; i.bindings_checked = False; i.boot_checked = True
        with unittest.mock.patch.object(inst.os, 'geteuid', return_value=0), unittest.mock.patch.object(inst.os, 'umask'), \
             unittest.mock.patch.object(inst.subprocess, 'run') as run:
            report = i.install()
            self.assertEqual(calls, ['refuse_if_active', 'account', 'directories', 'release', 'config', 'network', 'boot_policy', 'unit', 'verify'])
            self.assertFalse(report['started']); self.assertEqual(report['missions_created'], 0)
            self.assertFalse(any('start' in a.args[0] for a in run.call_args_list if a.args))


class ActuatorInvariant(unittest.TestCase):
    """The model reaches the world only through MCP; no tool there may act."""
    def test_model_tools_are_memory_skill_or_report_only(self):
        from memory_manager.phase2.mcp import advertised_tools
        names = [t['name'] for t in advertised_tools()] + ['jarvis_mission_result']
        self.assertTrue(names)
        for n in names:
            # 17.11: read-only real sources (host-side readers, GET-only HA; see sources/test_sources.py).
            self.assertRegex(n, r'^jarvis_(memory|skill|mission_result|ha_states$|ha_history$|influx_entities$|influx_series$)')
            self.assertIsNone(re.search(r'(service|call_service|shell|exec|command|http|homeassistant|switch|light|pump|relay|actuat|control|set_|turn)', n), n)

    def test_supervisor_egress_has_no_actuator_route(self):
        p = inst.egress_policy('192.0.2.96')
        allowed = [p['queue'], p['windows']]
        self.assertEqual(allowed, [['127.0.0.1', 8797], ['192.0.2.96', 22]])


if __name__ == '__main__':
    unittest.main()


aspec = importlib.util.spec_from_file_location('simple_arm', SIMPLE / 'arm.py')
arm = importlib.util.module_from_spec(aspec); aspec.loader.exec_module(arm)


class ArmPrivateService(unittest.TestCase):
    """Arming = the last commission step alone. Synthetic fixtures only (fake tokens)."""
    def setUp(self):
        import sqlite3
        self.d = Path(tempfile.mkdtemp()); self.addCleanup(__import__('shutil').rmtree, self.d)
        (self.d / 'pilot').mkdir(mode=0o700); (self.d / 'tokens').mkdir(); (self.d / 'backup').mkdir()
        self.tokens = {n: n.split('.')[0] + '-' + 'T' * 40 for n in arm.TOKEN_NAMES}
        for n, v in self.tokens.items(): self.write(self.d / 'tokens' / n, v + '\n')
        self.original = {'bridgeToken': 'B' * 40, 'syntheticOnly': True, 'dispatchEnabled': False, 'other': 1,
                         'operations': {'admissionEnabled': True, 'textEnabled': True, 'workerEnabled': False, 'voiceEnabled': False},
                         'missionLimits': {'calls': 6, 'tokens': 98304, 'seconds': 240, 'attempts': 1, 'remoteCostChf': 0},
                         'onDemand': {'accepting': True, 'executionEnabled': False, 'schedulerToken': 'S' * 40, 'runtime': None, 'commissioned': True}}
        self.write(self.d / 'pilot/config.json', json.dumps(self.original))
        self.write(self.d / 'identity.json', json.dumps({'schedulerToken': 'S' * 40, 'supervisorToken': 'O' * 40}))
        self.sup = {'identityFile': str(self.d / 'identity.json'), 'remoteCostChf': 0,
                    'runtimeIdentityHashes': {n: arm.sha(v.encode()) for n, v in self.tokens.items()}}
        self.write(self.d / 'sup.json', json.dumps(self.sup))
        with sqlite3.connect(self.d / 'pilot/memory.sqlite') as db:
            db.execute('CREATE TABLE p6q_jobs(mission_id TEXT, lease TEXT, cleanup_ok INTEGER)')
            db.execute('CREATE TABLE p2_outbox(mission_id TEXT, state TEXT)')
            db.execute("INSERT INTO p6q_jobs VALUES('m1', NULL, 1)"); db.execute("INSERT INTO p2_outbox VALUES('m1','ready')")
        self.calls = []; self.states = {arm.SUPERVISOR: 'active', arm.PILOT: 'active', arm.BOOT: 'active'}
        def ctl(*a):
            self.calls.append(a)
            if a[0] == 'stop': self.states[a[1]] = 'inactive'
            if a[0] == 'start': self.states[a[1]] = 'active'; self.states[arm.PILOT] = 'active'
            return __import__('types').SimpleNamespace(returncode=0, stdout='', stderr='')
        self.a = arm.Arm(self.d / 'pilot/config.json', self.d / 'sup.json', self.d / 'tokens', ctl=ctl, unit_state=lambda u: self.states.get(u, 'active'), backup_owner=(os.getuid(), os.getgid()),
                           wait_ports=lambda: self.calls.append(('wait-ports',)), journal=lambda: 'journal-tail')

    def write(self, p, text):
        p.write_text(text); os.chmod(p, 0o600)

    def test_profile_is_commission_execution_profile_verbatim(self):
        import ast
        tree = ast.parse((REPO / 'ops/demand/commission.py').read_text())
        fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'execution_profile')
        ns = {}; exec(compile(ast.Module([fn], []), 'commission-execution_profile', 'exec'), ns)
        self.assertEqual(arm.execution_profile(self.original, self.tokens, 'O' * 40), ns['execution_profile'](self.original, self.tokens, 'O' * 40))

    def test_check_is_read_only_and_never_shows_secrets(self):
        before = (self.d / 'pilot/config.json').read_bytes()
        raw, report = self.a.plan()
        self.assertEqual((self.d / 'pilot/config.json').read_bytes(), before); self.assertEqual(self.calls, [])
        self.assertNotIn('T' * 40, json.dumps(report)); self.assertNotIn('O' * 40, json.dumps(report))
        armed = json.loads(raw)
        self.assertEqual({k: v for k, v in armed.items() if k != 'onDemand'}, {k: v for k, v in self.original.items() if k != 'onDemand'})
        self.assertIs(armed['onDemand']['executionEnabled'], True)
        self.assertEqual(armed['onDemand']['runtime']['supervisorToken'], 'O' * 40)

    def test_refusals_before_any_write(self):
        cases = []
        def tamper(fn): cases.append(fn)
        tamper(lambda: self.write(self.d / 'tokens/model.token', 'other-' + 'X' * 40))                 # hash mismatch
        tamper(lambda: self.write(self.d / 'identity.json', json.dumps({'schedulerToken': 'Z' * 40, 'supervisorToken': 'O' * 40})))
        tamper(lambda: self.write(self.d / 'pilot/config.json', json.dumps({**self.original, 'onDemand': {**self.original['onDemand'], 'executionEnabled': True}})))  # already armed
        tamper(lambda: self.write(self.d / 'identity.json', json.dumps({'schedulerToken': 'S' * 40, 'supervisorToken': 'B' * 40})))  # shared identity
        tamper(lambda: __import__('sqlite3').connect(self.d / 'pilot/memory.sqlite').execute("UPDATE p6q_jobs SET cleanup_ok=0").connection.commit())
        tamper(lambda: os.chmod(self.d / 'tokens/hermes.token', 0o644))                                # not private
        for i, fn in enumerate(cases):
            self.setUp(); fn(); before = (self.d / 'pilot/config.json').read_bytes()
            with self.assertRaises((PermissionError, ValueError), msg=str(i)): self.a.apply(self.d / 'backup')
            self.assertEqual((self.d / 'pilot/config.json').read_bytes(), before, i); self.assertEqual(self.calls, [], i)
            self.assertFalse((self.d / 'backup' / arm.BACKUP_NAME).exists(), i)

    def test_apply_backup_arm_restart_then_disarm_restores_bytes(self):
        before = (self.d / 'pilot/config.json').read_bytes(); mode = (self.d / 'pilot/config.json').stat().st_mode
        r = self.a.apply(self.d / 'backup')
        self.assertTrue(r['armed']); self.assertEqual((self.d / 'backup' / arm.BACKUP_NAME).read_bytes(), before)
        # ports are awaited AFTER the private service stopped and BEFORE the boot hook starts it
        self.assertEqual(self.calls, [('stop', arm.SUPERVISOR), ('stop', arm.PILOT), ('stop', arm.BOOT), ('wait-ports',), ('start', arm.BOOT)])
        self.assertEqual((self.d / 'pilot/config.json').stat().st_mode, mode)
        with self.assertRaises((PermissionError, FileExistsError)): self.a.apply(self.d / 'backup')  # never arms twice
        self.calls.clear()
        out = self.a.disarm(self.d / 'backup')
        self.assertTrue(out['passed']); self.assertIs(out['executionEnabled'], False)
        self.assertEqual((self.d / 'pilot/config.json').read_bytes(), before)

    def test_failed_restart_restores_original_config(self):
        before = (self.d / 'pilot/config.json').read_bytes()
        self.a._restart_private = unittest.mock.Mock(side_effect=[False, True])
        with self.assertRaisesRegex(RuntimeError, 'original config restored.*journal-tail'): self.a.apply(self.d / 'backup')
        self.assertEqual((self.d / 'pilot/config.json').read_bytes(), before)
        # retry is possible after a restored failure (prod 16.11), the failed backup kept aside
        del self.a._restart_private
        self.assertTrue(self.a.apply(self.d / 'backup')['armed'])
        self.assertEqual(len(list((self.d / 'backup').glob('pilot-config.failed-attempt-*.json'))), 1)

    def test_port_refusal_during_restart_still_restores_original(self):
        """Rehearsal 16.11: a listener on 8797 made wait_ports RAISE; the armed config was left in place."""
        before = (self.d / 'pilot/config.json').read_bytes()
        self.states[arm.PILOT] = 'inactive'
        def busy(): raise PermissionError('Unexpected private-port listener')
        self.a.wait_ports = busy
        with self.assertRaisesRegex(RuntimeError, 'original config restored.*Unexpected private-port listener'): self.a.apply(self.d / 'backup')
        self.assertEqual((self.d / 'pilot/config.json').read_bytes(), before)
        self.assertNotIn(('start', arm.BOOT), self.calls)                    # never started over a foreign listener

    def test_wait_private_ports_waits_for_real_time_wait_and_refuses_listener(self):
        """Real kernel sockets: a server-side TIME_WAIT on the port blocks a raw bind
        (the coordinator's check); the wait must hold, a real listener must refuse."""
        import socket as so, threading
        srv = so.socket(); srv.bind(('127.0.0.1', 0)); srv.listen(1); port = srv.getsockname()[1]
        cli = so.create_connection(('127.0.0.1', port)); conn, _ = srv.accept()
        with self.assertRaises(PermissionError): arm.wait_private_ports(ports=(port,), seconds=0)   # listener present
        conn.close(); srv.close(); cli.recv(1); cli.close()          # server closes first -> TIME_WAIT on `port`
        probe = so.socket()
        with self.assertRaises(OSError): probe.bind(('127.0.0.1', port))
        probe.close()
        t = [0.0]
        with self.assertRaises(TimeoutError):
            arm.wait_private_ports(ports=(port,), seconds=1, clock=lambda: t[0], sleep=lambda d: t.__setitem__(0, t[0] + d))


class SupervisorJournal(unittest.TestCase):
    """Regression (prod 16.11): reserve refused 403 in a silent loop. Now one line per change."""
    def run_ticks(self, http, preflight, n):
        import io, contextlib
        from scripts import demand_supervisor as ds
        clock = [0.0]
        s = ds.Supervisor(http, preflight, lambda lease: {'cleanup_verified': True}, clock=lambda: clock[0])
        out = io.StringIO()
        def sleep(t): clock[0] += t
        with contextlib.redirect_stdout(out): ds.run_loop(s, sleep=sleep, ticks=n * 20)
        return [json.loads(l) for l in out.getvalue().splitlines() if l.startswith('{') and 'started' not in l]

    def test_refused_reservation_is_logged_once_with_its_stage(self):
        from memory_manager.phase2.local_model import Unavailable
        def http(method, path, body=None):
            if path == '/v1/queue/next': return {'job': {'mission_id': 'm1'}}
            raise Unavailable('Private endpoint unavailable')
        lines = self.run_ticks(http, lambda: None, 5)
        self.assertEqual(lines, [{'event': 'supervisor-error', 'stage': 'reserve', 'error_type': 'Unavailable', 'error': 'Private endpoint unavailable'}])

    def test_preflight_failure_reason_and_cause_logged_once(self):
        calls = []
        def http(method, path, body=None):
            calls.append(path); return {'job': {'mission_id': 'm1'}} if path == '/v1/queue/next' else {'deferred': True}
        def preflight(): raise PermissionError('Existing Windows application differs: x; do not patch implicitly')
        lines = self.run_ticks(http, preflight, 3)
        self.assertEqual(len(lines), 1); self.assertEqual(lines[0]['reason'], 'preflight_failed')
        self.assertIn('PermissionError: Existing Windows application differs', lines[0]['preflight_error'])
        self.assertEqual(calls.count('/v1/queue/defer'), calls.count('/v1/queue/next'))  # deferred at every tick, logged once


uspec = importlib.util.spec_from_file_location('simple_private_update', SIMPLE / 'private_update.py')
pupd = importlib.util.module_from_spec(uspec); uspec.loader.exec_module(pupd)


class PrivateUpdate(unittest.TestCase):
    """Targeted private-release update: exact base only, exhaustive pins, candidate verify_manifest, reversible."""
    def setUp(self):
        import shutil, sqlite3, subprocess, types
        self.d = Path(tempfile.mkdtemp()); self.addCleanup(shutil.rmtree, self.d)
        self.root = self.d / 'opt'; (self.d / 'state').mkdir(); (self.d / 'backup').mkdir()
        shutil.copytree(REPO / 'memory_manager', self.root / 'memory_manager', ignore=shutil.ignore_patterns('__pycache__', 'test_*'))
        (self.root / 'scripts').mkdir(); shutil.copyfile(REPO / pupd.VERIFIER, self.root / pupd.VERIFIER)
        self.new = [n for n, b in pupd.FILES.items() if b is None]          # files the step creates
        self.existing = [n for n, b in pupd.FILES.items() if b]
        for name in self.new:
            if (self.root / name).exists(): (self.root / name).unlink()
        for name in {str(Path(n).parent) for n in self.new}:
            if (self.root / name).is_dir() and not any((self.root / name).iterdir()): (self.root / name).rmdir()
        for name in self.existing:                                  # installed = reviewed base of the last step
            (self.root / name).write_bytes(subprocess.check_output(['git', 'show', pupd.BASE_COMMIT + ':' + name], cwd=REPO))
        pinned = [*self.existing, 'memory_manager/__init__.py']
        pilot = {'mode': 'synthetic-interactive-queue-only', 'files': {f: pupd.sha((self.root / f).read_bytes()) for f in pinned}}
        (self.root / 'docs/pilot-interactive').mkdir(parents=True)
        (self.root / pupd.PILOT_MANIFEST).write_text(json.dumps(pilot))
        deploy = {f: pupd.sha((self.root / f).read_bytes()) for f in [*pinned, pupd.PILOT_MANIFEST, pupd.VERIFIER]}
        (self.root / pupd.DEPLOY).write_text(json.dumps(deploy))
        for f in [*pinned, pupd.PILOT_MANIFEST, pupd.DEPLOY]: os.chmod(self.root / f, 0o444)
        with sqlite3.connect(self.d / 'state/memory.sqlite') as db:
            db.execute('CREATE TABLE p6q_jobs(mission_id TEXT, lease TEXT, cleanup_ok INTEGER)'); db.execute('CREATE TABLE p2_outbox(mission_id TEXT, state TEXT)')
        self.calls = []; self.restart_ok = [True]
        r = types.SimpleNamespace(state=lambda u: 'active', ctl=lambda *a: self.calls.append(a), last_error=None,
                                  _stop_supervisor_if_idle=lambda: self.calls.append(('stop-supervisor',)),
                                  _restart_private=lambda: self.calls.append(('restart',)) or self.restart_ok.pop(0))
        self.u = pupd.Update(REPO, self.root, self.d / 'state', restarter=r, owner=os.getuid(), journal=lambda u: 'journal-' + u)
        self.tracked = [*pupd.FILES, pupd.PILOT_MANIFEST, pupd.DEPLOY]

    def snapshot(self): return {n: (self.root / n).read_bytes() if (self.root / n).exists() else None for n in self.tracked}

    def test_base_hashes_are_the_accord3_release_then_each_previous_step(self):
        import subprocess
        doc = json.loads((REPO / 'docs/HERMES_ON_DEMAND_MANIFEST.json').read_text())
        delta = {r['path']: r['after'] for r in doc['private_delta']}
        first = pupd.STEPS[0][2]
        self.assertEqual(first['memory_manager/phase2/bridge.py'], delta['memory_manager/phase2/bridge.py'])
        ops = json.loads((REPO / 'docs/HERMES_OPERATIONAL_MANIFEST.json').read_text())['files']
        self.assertEqual(first['memory_manager/phase3/model_gate.py'], ops['pilot-release/memory_manager/phase3/model_gate.py'])
        for sub, commit, files in pupd.STEPS:                      # each base = that commit's file (prod-verified 17.11 for 2e4859d)
            for name, base in files.items():
                if base is None:                                     # new file: absent at that commit
                    self.assertNotEqual(subprocess.run(['git', 'cat-file', '-e', commit + ':' + name], cwd=REPO).returncode, 0, name); continue
                self.assertEqual(pupd.sha(subprocess.check_output(['git', 'show', commit + ':' + name], cwd=REPO)), base, (sub, name))
        self.assertEqual(len({s[0] for s in pupd.STEPS}), len(pupd.STEPS))

    def test_next_step_follows_what_is_installed(self):
        steps = {sub: files for sub, _, files in pupd.STEPS}
        behind = {n: b for n, b in steps['private-update-6'].items()}            # prod one step behind
        self.assertEqual(self.u.next_step(behind)[0], 'private-update-6')
        self.assertEqual(self.u.next_step(dict(pupd.FILES))[0], pupd.BACKUP_SUB)
        current = {n: pupd.sha((REPO / n).read_bytes()) for n in pupd.FILES}
        with self.assertRaisesRegex(PermissionError, 'Already updated'): self.u.next_step(current)

    def test_check_runs_release_verify_manifest_and_writes_nothing(self):
        before = self.snapshot()
        _, report = self.u.plan()
        self.assertEqual(report['candidate_test'], 'verify_manifest ok, imports ok'); self.assertEqual(report['pins_found'], 1 + 2 * len(self.existing))
        self.assertEqual(self.snapshot(), before); self.assertEqual(self.calls, [])

    def test_unexpected_pin_is_refused(self):
        (self.root / 'docs/other.json').write_text(json.dumps({'x': self.existing and pupd.FILES[self.existing[0]]}))
        with self.assertRaisesRegex(PermissionError, 'Unexpected pins.*docs/other.json'): self.u.plan()

    def test_candidate_failing_verify_manifest_is_refused(self):
        p = self.root / 'memory_manager/__init__.py'; os.chmod(p, 0o644); p.write_bytes(p.read_bytes() + b'# drift\n'); os.chmod(p, 0o444)
        with self.assertRaisesRegex(RuntimeError, 'Candidate refused'): self.u.plan()

    def test_refuses_unknown_installed_version(self):
        p = self.root / self.existing[0]; os.chmod(p, 0o644); p.write_bytes(b'# drift\n'); os.chmod(p, 0o444)
        with self.assertRaisesRegex(PermissionError, 'Installed file differs'): self.u.apply(self.d / 'backup')
        self.assertFalse((self.d / 'backup' / pupd.BACKUP_SUB).exists()); self.assertEqual(self.calls, [])

    def test_apply_cascades_both_manifests_then_revert_exact(self):
        before = self.snapshot()
        self.assertTrue(self.u.apply(self.d / 'backup')['updated'])
        deploy = json.loads((self.root / pupd.DEPLOY).read_text()); pilot = json.loads((self.root / pupd.PILOT_MANIFEST).read_text())
        for n in pupd.FILES:
            new = pupd.sha((REPO / n).read_bytes())
            self.assertEqual((self.root / n).read_bytes(), (REPO / n).read_bytes())
            self.assertEqual((deploy[n], pilot['files'][n]), (new, new)); self.assertEqual((self.root / n).stat().st_mode & 0o777, 0o444)
        self.assertEqual(deploy[pupd.PILOT_MANIFEST], pupd.sha((self.root / pupd.PILOT_MANIFEST).read_bytes()))
        self.assertEqual(pilot['mode'], 'synthetic-interactive-queue-only')
        self.assertEqual(self.calls, [('stop-supervisor',), ('stop', pupd.arm.PILOT), ('restart',)])
        self.restart_ok = [True]
        out = self.u.revert(self.d / 'backup')
        self.assertTrue(out['passed']); self.assertEqual(out['removed_files'], sorted(self.new))
        self.assertEqual(self.snapshot(), before)
        for n in self.new: self.assertFalse((self.root / n).parent.exists(), n)       # created directory removed too

    def test_new_file_already_present_is_refused(self):
        if not self.new: self.skipTest('no new file in the last step')
        p = self.root / self.new[0]; p.parent.mkdir(exist_ok=True); p.write_bytes(b'')
        with self.assertRaisesRegex(PermissionError, 'New file already present'): self.u.plan()

    def test_failed_restart_restores_and_reports_failed_attempt_journals(self):
        before = self.snapshot(); self.restart_ok = [False, True]
        with self.assertRaisesRegex(RuntimeError, 'previous files restored.*journal-jarvis-hermes-private-boot.*journal-jarvis-hermes-pilot-system'):
            self.u.apply(self.d / 'backup')
        self.assertEqual(self.snapshot(), before)

    def test_retry_after_restored_failure_sets_old_backup_aside(self):
        self.restart_ok = [False, True]
        with self.assertRaises(RuntimeError): self.u.apply(self.d / 'backup')
        self.restart_ok = [True]
        self.assertTrue(self.u.apply(self.d / 'backup')['updated'])
        self.assertEqual(len(list((self.d / 'backup').glob(pupd.BACKUP_SUB + '.failed-attempt-*'))), 1)
        with self.assertRaises((PermissionError, FileExistsError)): self.u.apply(self.d / 'backup')  # never twice over a real update

    def test_revert_undoes_latest_step_first_and_keeps_earlier_ones(self):
        import shutil
        prev = self.d / 'backup' / pupd.STEPS[0][0]                  # an earlier, still-applied step
        shutil.copytree(self.root, prev, ignore=lambda d, n: [x for x in n if x not in ('memory_manager', 'phase2', 'bridge.py', 'docs', 'pilot-interactive', 'manifest.json', pupd.DEPLOY)])
        before = self.snapshot()
        self.assertTrue(self.u.apply(self.d / 'backup')['updated'])
        self.assertEqual(pupd.Update.pending(self.d / 'backup'), [pupd.BACKUP_SUB, pupd.STEPS[0][0]])
        self.restart_ok = [True]
        out = self.u.revert(self.d / 'backup')
        self.assertEqual((out['step'], out['still_applied']), (pupd.BACKUP_SUB, [pupd.STEPS[0][0]]))
        self.assertEqual(self.snapshot(), before)


fspec = importlib.util.spec_from_file_location('simple_frontend_update', SIMPLE / 'frontend_update.py')
fup = importlib.util.module_from_spec(fspec); fspec.loader.exec_module(fup)


class FrontendUpdate(unittest.TestCase):
    """Stacked gateway-asset updates: exact base only, HTTPS-verified, auto-restore, revert latest first."""
    def setUp(self):
        import pwd, shutil
        self.d = Path(tempfile.mkdtemp()); self.addCleanup(shutil.rmtree, self.d); (self.d / 'backup').mkdir()
        self.pub = self.d / 'public/jarvis'; self.pub.mkdir(parents=True)
        self.base_js = ('const a=1;if(reportQuality){const quality=JSON.parse(reportQuality.data);' + fup.OLD + '\nconst b=2;').encode()
        self.base_css = b'#hermesMissionsDialog{color:red}'
        self.v1 = fup.candidate(self.base_js); self.v2 = {fup.JS: b'// ui v2', fup.CSS: b'/* ui v2 */'}
        self.steps = [('frontend-update', {fup.JS: (fup.sha(self.base_js), fup.sha(self.v1), fup.candidate)}),
                      ('frontend-update-2', {fup.JS: (fup.sha(self.v1), fup.sha(self.v2[fup.JS]), lambda raw: self.v2[fup.JS]),
                                             fup.CSS: (fup.sha(self.base_css), fup.sha(self.v2[fup.CSS]), lambda raw: self.v2[fup.CSS])})]
        self.put(fup.JS, self.base_js); self.put(fup.CSS, self.base_css)
        os.chmod(self.pub / fup.CSS, 0o600)                                              # as in prod
        self.served = {}
        fetch = lambda name: self.served.pop(name) if name in self.served else (200, fup.sha((self.pub / name).read_bytes()))
        self.u1 = fup.Update(self.pub, pwd.getpwuid(os.getuid()), fetch=fetch, steps=self.steps[:1])
        self.u2 = fup.Update(self.pub, pwd.getpwuid(os.getuid()), fetch=fetch, steps=self.steps)
    def put(self, name, raw): p = self.pub / name; p.write_bytes(raw); os.chmod(p, 0o644)
    def files(self): return {n: (self.pub / n).read_bytes() for n in (fup.JS, fup.CSS)}

    def test_applies_the_step_matching_the_installed_files_in_order(self):
        self.assertEqual(self.u2.apply(self.d / 'backup')['step'], 'frontend-update')      # still before step 1
        self.assertEqual(self.u2.apply(self.d / 'backup')['step'], 'frontend-update-2')
        self.assertEqual(self.files(), self.v2)
        with self.assertRaisesRegex(PermissionError, 'Already updated'): self.u2.plan()

    def test_pinned_steps_match_reviewed_sources(self):
        doc = json.loads((REPO / 'docs/HERMES_ON_DEMAND_MANIFEST.json').read_text())
        (sub1, f1), (sub2, f2), (sub3, f3), (sub4, f4) = fup.STEPS
        self.assertEqual(f1[fup.JS][0], doc['frontend']['after'])                     # installed on-demand frontend
        self.assertEqual(f2[fup.JS][0], f1[fup.JS][1])                                 # step 2 starts where step 1 ends
        self.assertEqual(f3[fup.JS][0], f2[fup.JS][1])                                 # step 3 starts where step 2 ends
        for name in (fup.JS, fup.CSS):                                                 # step 2 still builds its reviewed bytes
            self.assertEqual(fup.sha(f2[name][2](b'')), f2[name][1], name)
        self.assertEqual(fup.sha(f3[fup.JS][2](b'')), f3[fup.JS][1])                     # step 3 still builds its reviewed bytes (b9b86be)
        self.assertEqual(f4[fup.JS][0], f3[fup.JS][1])                                 # step 4 starts where step 3 ends
        self.assertEqual(f4[fup.JS][1], fup.sha((REPO / 'ops/hermes-ui/hermes-embedded.js').read_bytes()), 'pin step 4 after editing ops/hermes-ui')
        lot_a = json.loads((REPO / 'docs/JARVIS_2_BIG_BOSS_LOT_A_RESULTS.json').read_text())
        css = next(r for r in lot_a['files'] if r['target'].endswith(fup.CSS))
        self.assertEqual(f2[fup.CSS][0], css['after_sha256'])

    def test_step1_patch_once_and_refuses_drift_or_mode(self):
        self.assertTrue(self.u1.plan()[1]['passed']); self.assertEqual(self.files()[fup.JS], self.base_js)
        with self.assertRaises(PermissionError): fup.candidate(self.base_js + fup.OLD.encode())
        os.chmod(self.pub / fup.JS, 0o664)
        with self.assertRaisesRegex(PermissionError, 'mode 0600 or 0644'): self.u1.plan()
        self.put(fup.JS, self.base_js + b'//')
        with self.assertRaisesRegex(PermissionError, 'reviewed base'): self.u1.plan()

    def test_stacked_apply_then_revert_latest_first_exact(self):
        before = self.files()
        self.assertTrue(self.u1.apply(self.d / 'backup')['updated']); after1 = self.files()
        r = self.u2.apply(self.d / 'backup'); self.assertEqual((r['step'], r['https_verified']), ('frontend-update-2', [fup.CSS, fup.JS]))
        self.assertEqual(self.files(), self.v2); self.assertEqual(self.u2.pending(self.d / 'backup'), ['frontend-update-2', 'frontend-update'])
        self.assertEqual(((self.pub / fup.JS).stat().st_mode & 0o777, (self.pub / fup.CSS).stat().st_mode & 0o777), (0o644, 0o600))  # modes kept (prod 17.11)
        with self.assertRaisesRegex(PermissionError, 'Already updated'): self.u2.apply(self.d / 'backup')
        out = self.u2.revert(self.d / 'backup'); self.assertEqual((out['step'], out['still_applied']), ('frontend-update-2', ['frontend-update']))
        self.assertEqual(self.files(), after1)
        self.u2.revert(self.d / 'backup'); self.assertEqual(self.files(), before)
        self.assertEqual((self.pub / fup.CSS).stat().st_mode & 0o777, 0o600)
        with self.assertRaises(FileNotFoundError): self.u2.revert(self.d / 'backup')

    def test_any_served_mismatch_restores_both_files(self):
        self.u1.apply(self.d / 'backup'); after1 = self.files()
        self.served = {fup.JS: (200, 'stale')}
        with self.assertRaisesRegex(RuntimeError, 'previous files restored'): self.u2.apply(self.d / 'backup')
        self.assertEqual(self.files(), after1)
        self.assertTrue(self.u2.apply(self.d / 'backup')['updated'])                  # retry sets the identical backup aside
        self.assertEqual(len(list((self.d / 'backup').glob('frontend-update-2.failed-attempt-*'))), 1)

    def test_route_step4_real_files_prod_20261118(self):
        # Real step 4 over the prod bases: panel e656c1a4 (step 3), app.js / codex-voice.js @ 2d40cc2.
        import subprocess
        git = lambda rev: subprocess.run(['git', 'show', rev], cwd=SIMPLE.parents[1], capture_output=True, check=True).stdout
        self.put(fup.JS, git('b9b86be:ops/hermes-ui/hermes-embedded.js'))
        self.put(fup.APP, git('2d40cc2:public/app.js')); self.put(fup.VOICE, git('2d40cc2:public/codex-voice.js'))
        order = []
        u = fup.Update(self.pub, __import__('pwd').getpwuid(os.getuid()), fetch=lambda n: (200, fup.sha((self.pub / n).read_bytes())), steps=fup.STEPS)
        write = u._write; u._write = lambda n, raw: (order.append(n), write(n, raw))
        r = u.apply(self.d / 'backup')
        self.assertEqual(r['step'], 'frontend-update-4'); self.assertEqual(order, [fup.JS, fup.APP, fup.VOICE][:1] + sorted([fup.APP, fup.VOICE]))
        for n, want in ((fup.JS, fup.JS4), (fup.APP, fup.APP4), (fup.VOICE, fup.VOICE4)): self.assertEqual(fup.sha((self.pub / n).read_bytes()), want)
        app = (self.pub / fup.APP).read_text()
        self.assertIn('void hermesHandoff(r.hermes.question', app); self.assertIn('JarvisHermesDelegate', app)
        with self.assertRaisesRegex(PermissionError, 'Already updated'): u.plan()
        out = u.revert(self.d / 'backup'); self.assertEqual(out['step'], 'frontend-update-4')
        self.assertEqual((self.pub / fup.APP).read_bytes(), git('2d40cc2:public/app.js'))

    def test_revert_refuses_over_an_unknown_version(self):
        self.u1.apply(self.d / 'backup'); self.u2.apply(self.d / 'backup'); self.put(fup.CSS, b'other')
        with self.assertRaisesRegex(PermissionError, 'not the result'): self.u2.revert(self.d / 'backup')
        self.assertEqual(self.files()[fup.CSS], b'other')


rspec = importlib.util.spec_from_file_location('simple_route_update', SIMPLE / 'route_update.py')
rup = importlib.util.module_from_spec(rspec); rspec.loader.exec_module(rup)


class RouteUpdate(unittest.TestCase):
    """18.11 route 3: one backend file, exact base only, refused until the browser side is served."""
    def setUp(self):
        import shutil, subprocess
        self.d = Path(tempfile.mkdtemp()); self.addCleanup(shutil.rmtree, self.d)
        self.t = self.d / 'hybrid-brain.mjs'
        self.t.write_bytes(subprocess.run(['git', 'show', '2d40cc2:hybrid-brain.mjs'], cwd=SIMPLE.parents[1], capture_output=True, check=True).stdout); os.chmod(self.t, 0o664)
        self.served = (200, 'old')
        self.r = rup.Route(self.t, served_app=lambda: self.served)

    def test_refused_before_frontend_then_applied_and_reverted(self):
        self.assertEqual(self.r.plan()[1]['before'], rup.BASE)
        with self.assertRaisesRegex(PermissionError, 'frontend-update-4 first'): self.r.apply(self.d / 'b')
        self.assertEqual(rup.sha(self.t.read_bytes()), rup.BASE)
        self.served = (200, fup.APP4)
        out = self.r.apply(self.d / 'b'); self.assertTrue(out['updated']); self.assertIn("'hermes'", self.t.read_text()); self.assertEqual(os.stat(self.t).st_mode & 0o777, 0o664)
        with self.assertRaisesRegex(PermissionError, 'Already updated'): self.r.plan()
        self.assertTrue(self.r.revert(self.d / 'b')['passed']); self.assertEqual(rup.sha(self.t.read_bytes()), rup.BASE)

    def test_unknown_base_refused(self):
        self.t.write_bytes(self.t.read_bytes() + b'//'); self.served = (200, fup.APP4)
        with self.assertRaisesRegex(PermissionError, 'reviewed base'): self.r.plan()
