"""Supervisor Windows bindings: only the two MCP entries and bindingsSha256 change; exact base; reversible."""
import hashlib, importlib.util, json, os, tempfile, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('bindings_update', ROOT / 'ops/demand-simple/bindings_update.py')
bu = importlib.util.module_from_spec(spec); spec.loader.exec_module(bu)
sha = lambda raw: hashlib.sha256(raw).hexdigest()
MCP = sorted({n for _, c in bu.STEPS[:2] for n in c})      # 17.11 steps (bindings-update, -2)


class BindingsUpdate(unittest.TestCase):
    def setUp(self):
        self.d = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__('shutil').rmtree(self.d))
        first = bu.STEPS[0][1]                                      # prod before 17.11: release eb17c0c
        host = {**first, 'memory_manager/phase4/job.py': 'j' * 64}
        win = {'memory_manager/phase2/mcp.py': 'a' * 64, 'memory_manager/phase3/mcp.py': first['memory_manager/phase3/mcp.py'], 'memory_manager/phase4/job.py': 'w' * 64}
        self.bfile = self.d / 'windows-bindings.json'
        self.braw = json.dumps({'profile': 'operational-8797', 'host_files': host, 'windows_files': win}).encode()
        self.bfile.write_bytes(self.braw); os.chmod(self.bfile, 0o600)
        import subprocess
        self.opt = self.d / 'opt'
        for n in bu.NAMES:
            (self.opt / n).parent.mkdir(parents=True, exist_ok=True)
            (self.opt / n).write_bytes(subprocess.check_output(['git', 'show', '72391f3:' + n], cwd=ROOT)); os.chmod(self.opt / n, 0o640)
        self.cfg = self.d / 'config.json'
        src = {'x': 'y', 'memory_manager/phase3/mcp.py': first['memory_manager/phase3/mcp.py']}
        self.craw = (json.dumps({'enabled': False, 'bindingsFile': str(self.bfile), 'bindingsSha256': sha(self.braw), 'sourceFiles': src}, indent=1, sort_keys=True) + '\n').encode()
        self.cfg.write_bytes(self.craw); os.chmod(self.cfg, 0o600)
        self.state = ['inactive']
        self.b = bu.Bindings(ROOT, self.cfg, self.opt, unit_state=lambda: self.state[0])
        self.opt_before = {n: (self.opt / n).read_bytes() for n in bu.NAMES}

    def test_apply_changes_only_two_entries_then_revert(self):
        out = self.b.apply(self.d / 'bk')
        new = json.loads(self.bfile.read_text()); cfg = json.loads(self.cfg.read_text())
        for n in MCP:
            want = sha((ROOT / n).read_bytes())
            self.assertEqual((new['host_files'][n], new['windows_files'][n]), (want, want))
        self.assertEqual((new['host_files']['memory_manager/phase4/job.py'], new['windows_files']['memory_manager/phase4/job.py']), ('j' * 64, 'w' * 64))
        self.assertEqual(cfg['bindingsSha256'], sha(self.bfile.read_bytes()))
        p3 = 'memory_manager/phase3/mcp.py'
        self.assertEqual(cfg['sourceFiles'], {'x': 'y', p3: sha((ROOT / p3).read_bytes())})
        for n in MCP:
            self.assertEqual((self.opt / n).read_bytes(), (ROOT / n).read_bytes()); self.assertEqual((self.opt / n).stat().st_mode & 0o777, 0o640)
        self.assertEqual(out['config_keys_changed'], ['bindingsSha256', 'sourceFiles'])
        self.assertEqual(self.bfile.stat().st_mode & 0o777, 0o600)
        with self.assertRaisesRegex(PermissionError, 'Already updated'): self.b.plan()
        self.b.revert(self.d / 'bk')
        self.assertEqual((self.bfile.read_bytes(), self.cfg.read_bytes()), (self.braw, self.craw))
        self.assertEqual({n: (self.opt / n).read_bytes() for n in bu.NAMES}, self.opt_before)

    def test_supervisor_copy_drift_refused(self):
        p = self.opt / 'memory_manager/phase2/mcp.py'; p.write_bytes(b'# drift')
        with self.assertRaisesRegex(PermissionError, 'Supervisor copy'): self.b.plan()

    def test_second_step_when_prod_already_has_the_first(self):
        import subprocess
        p2, p3 = 'memory_manager/phase2/mcp.py', 'memory_manager/phase3/mcp.py'
        for n in (p2, p3): (self.opt / n).write_bytes(subprocess.check_output(['git', 'show', '7b654f1:' + n], cwd=ROOT))
        b = json.loads(self.braw); h = {n: sha((self.opt / n).read_bytes()) for n in (p2, p3)}
        b['host_files'].update(h); b['windows_files'].update(h); raw = json.dumps(b).encode(); self.bfile.write_bytes(raw)
        cfg = json.loads(self.craw); cfg['bindingsSha256'] = sha(raw); cfg['sourceFiles'][p3] = h[p3]
        self.cfg.write_bytes((json.dumps(cfg, indent=1, sort_keys=True) + '\n').encode())
        out = self.b.apply(self.d / 'bk')
        self.assertEqual((out['step'], [r['file'] for r in out['files']]), ('bindings-update-2', [p2]))
        self.assertEqual(json.loads(self.bfile.read_text())['windows_files'][p2], sha((ROOT / p2).read_bytes()))
        self.assertEqual(bu.Bindings.pending(self.d / 'bk'), ['bindings-update-2'])
        self.b.revert(self.d / 'bk'); self.assertEqual(self.bfile.read_bytes(), raw)

    def test_refusals(self):
        self.state[0] = 'active'
        with self.assertRaisesRegex(PermissionError, 'must be stopped'): self.b.apply(self.d / 'bk')
        self.state[0] = 'inactive'
        b = json.loads(self.braw); b['host_files']['memory_manager/phase2/mcp.py'] = 'z' * 64
        raw = json.dumps(b).encode(); self.bfile.write_bytes(raw)
        with self.assertRaisesRegex(PermissionError, 'differ from bindingsSha256'): self.b.plan()
        self.cfg.write_bytes(self.craw.replace(sha(self.braw).encode(), sha(raw).encode()))
        with self.assertRaisesRegex(PermissionError, 'not the reviewed base'): self.b.plan()


if __name__ == '__main__':
    unittest.main()


class MiningStep(unittest.TestCase):
    """18.11 bindings-update-3: supervisor-only files keep no Windows binding; the Windows Ollama guard does."""
    def test_pins_updated_only_where_present_then_reverted(self):
        import shutil, subprocess
        d = Path(tempfile.mkdtemp()); self.addCleanup(shutil.rmtree, d)
        names = bu.STEPS[-1][1]; sup, life, win = 'scripts/demand_supervisor.py', 'scripts/pilot_phase4_windows.py', 'ops/phase4-run-ollama-windows.py'
        mcp_now = {n: sha((ROOT / n).read_bytes()) for n in MCP}                          # prod already has the 17.11 steps
        host = {**mcp_now, win: names[win]}; windows = {**mcp_now, win: names[win]}
        bfile = d / 'b.json'; braw = json.dumps({'host_files': host, 'windows_files': windows}).encode(); bfile.write_bytes(braw); os.chmod(bfile, 0o600)
        cfg = d / 'c.json'; src = {sup: names[sup], life: names[life], win: names[win], 'other.py': 'o' * 64}
        craw = (json.dumps({'bindingsFile': str(bfile), 'bindingsSha256': sha(braw), 'sourceFiles': src}, indent=1, sort_keys=True) + '\n').encode()
        cfg.write_bytes(craw); os.chmod(cfg, 0o600)
        opt = d / 'opt'
        for n in bu.NAMES:
            (opt / n).parent.mkdir(parents=True, exist_ok=True)
            (opt / n).write_bytes(subprocess.check_output(['git', 'show', 'ef15837:' + n], cwd=ROOT)); os.chmod(opt / n, 0o640)
        b = bu.Bindings(ROOT, cfg, opt, unit_state=lambda: 'inactive')
        out = b.apply(d / 'bk'); self.assertEqual(out['step'], 'bindings-update-3')
        rows = {r['file']: r for r in out['files']}; self.assertEqual([n for n, r in rows.items() if r['copy_to_windows']], [win])
        nb, nc = json.loads(bfile.read_text()), json.loads(cfg.read_text())
        self.assertNotIn(sup, nb['windows_files']); self.assertNotIn(sup, nb['host_files'])
        for n in (sup, life, win): self.assertEqual(nc['sourceFiles'][n], sha((ROOT / n).read_bytes())); self.assertEqual((opt / n).read_bytes(), (ROOT / n).read_bytes())
        self.assertEqual(nb['windows_files'][win], sha((ROOT / win).read_bytes())); self.assertEqual(nc['sourceFiles']['other.py'], 'o' * 64)
        self.assertEqual(nc['bindingsSha256'], sha(bfile.read_bytes()))
        with self.assertRaisesRegex(PermissionError, 'Already updated'): b.plan()
        b.revert(d / 'bk'); self.assertEqual((bfile.read_bytes(), cfg.read_bytes()), (braw, craw))

