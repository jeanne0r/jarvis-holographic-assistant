"""Synthetic resource-policy/telemetry tests. No hypervisor or guest actions."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from . import lab, sizing


class Sizing(unittest.TestCase):
    def rows(self):
        return [{'at': 100 + i * 2, 'mem_available_bytes': 4352 * sizing.MIB,
                 'balloon_growth_bytes': 0, 'psi_full_avg10': 0.0, 'pswpout': 123} for i in range(15)]

    def test_budgets_preserve_host_reserve_and_include_virtualization(self):
        three, two = sizing.plan(), sizing.plan(2048)
        self.assertEqual(three['runtime_max_mib'], 2048)
        self.assertEqual(two['runtime_max_mib'], 1024)
        self.assertEqual(three['host_required_bytes'], 4352 * sizing.MIB)
        self.assertEqual(two['host_required_bytes'], 3328 * sizing.MIB)
        self.assertTrue(three['runtime_limit_previously_exercised'])
        self.assertFalse(two['runtime_limit_previously_exercised'])
        self.assertFalse(three['target_vm_size_tested'])
        with self.assertRaises(ValueError): sizing.plan(4096)

    def test_reinflation_is_reserved_without_changing_other_guests(self):
        state = {'guests': {'103': {'maximum_mib': 4096, 'actual_bytes': 4096 * sizing.MIB},
                            '201': {'maximum_mib': 2048, 'actual_bytes': 1024 * sizing.MIB}}}
        growth = sizing.balloon_growth(state)
        self.assertEqual(growth, 1024 * sizing.MIB)
        self.assertEqual(sizing.plan(balloon_growth_bytes=growth)['host_required_bytes'], 5376 * sizing.MIB)
        self.assertEqual(state['guests']['201']['actual_bytes'], 1024 * sizing.MIB)

    def test_only_sustained_fresh_admission_is_accepted(self):
        rows = self.rows()
        self.assertTrue(sizing.admission(rows, now=129)['admitted'])
        self.assertFalse(sizing.admission(rows, now=200)['admitted'])
        self.assertFalse(sizing.admission(rows[:5], now=129)['admitted'])
        rows[8]['at'] += 4
        self.assertFalse(sizing.admission(rows, now=129)['admitted'])

    def test_one_low_capacity_sample_or_balloon_growth_blocks_admission(self):
        rows = self.rows(); rows[5]['mem_available_bytes'] -= 1
        self.assertEqual(sizing.admission(rows, now=129)['reason'], 'host_capacity')
        rows = self.rows(); rows[5]['balloon_growth_bytes'] = sizing.MIB
        self.assertEqual(sizing.admission(rows, now=129)['reason'], 'host_capacity')

    def test_swap_pressure_and_unknown_metrics_block_admission(self):
        rows = self.rows(); rows[-1]['pswpout'] += 1
        self.assertFalse(sizing.admission(rows, now=129)['admitted'])
        for value in (None, float('nan'), float('inf'), True):
            rows = self.rows(); rows[0]['psi_full_avg10'] = value
            self.assertFalse(sizing.admission(rows, now=129)['admitted'])
        rows = self.rows(); rows[0]['psi_full_avg10'] = 1.1
        self.assertFalse(sizing.admission(rows, now=129)['admitted'])


class Observation(unittest.TestCase):
    def setUp(self):
        spec = importlib.util.spec_from_file_location('memory_observe', lab.ROOT / 'ops/phase3-memory-observe.py')
        self.ops = importlib.util.module_from_spec(spec); spec.loader.exec_module(self.ops)
        parent = lab.ROOT / 'data/phase3'; parent.mkdir(parents=True, exist_ok=True)
        self.tmp = tempfile.TemporaryDirectory(dir=parent); self.root = Path(self.tmp.name)

    def tearDown(self): self.tmp.cleanup()

    def put(self, path, content):
        p = self.root / path; p.parent.mkdir(parents=True, exist_ok=True); p.write_text(content)

    def test_records_cgroup_peak_events_rss_and_individual_hwm(self):
        self.put('proc/meminfo', 'MemTotal: 3000000 kB\nMemAvailable: 2000000 kB\nSwapFree: 0 kB\n')
        self.put('proc/vmstat', 'pswpout 5\noom_kill 0\n')
        self.put('proc/pressure/memory', 'full avg10=0.00 avg60=0.00 avg300=0.00 total=0\n')
        cg = 'sys/fs/cgroup/system.slice/jarvis-phase3-hermes.service/'
        for name, value in {'memory.current': '100', 'memory.peak': '200', 'memory.events': 'oom 1\noom_kill 1\n',
                            'cgroup.procs': '42\n', 'memory.swap.current': '0', 'memory.stat': 'anon 90\nfile 10\n'}.items():
            self.put(cg + name, value)
        self.put('proc/42/status', 'Name: python\nVmRSS: 32 kB\nVmHWM: 64 kB\n')
        sample = self.ops.snapshot('guest', self.root)
        self.assertEqual(sample['cgroup_peak_bytes'], 200)
        self.assertEqual(sample['cgroup_events']['oom_kill'], 1)
        self.assertEqual(sample['rss_sum_bytes'], 32 * 1024)
        self.assertEqual(sample['processes'][0]['hwm_bytes'], 64 * 1024)
        self.assertEqual(sample['pswpout'], 5)

    def test_absent_cgroup_or_counter_never_claims_zero_oom_or_peak(self):
        sample = self.ops.snapshot('guest', self.root)
        self.assertFalse(sample['cgroup_present'])
        self.assertIsNone(sample['cgroup_events'])
        self.assertIsNone(sample['cgroup_peak_bytes'])
        self.assertIsNone(sample['rss_sum_bytes'])
        self.assertIsNone(sample['oom_kill_vmstat'])

    def test_observer_artifact_is_private_and_never_overwritten(self):
        output = self.root / 'samples.jsonl'
        args = ['observe', '--role', 'guest', '--count', '1', '--output', str(output)]
        with patch('sys.argv', args), patch.object(self.ops.socket, 'gethostname', return_value='jarvis-lab'), \
             patch.object(self.ops, 'snapshot', return_value={'test': True}):
            self.ops.main()
            before = output.read_bytes()
            with self.assertRaises(FileExistsError): self.ops.main()
        self.assertEqual(output.read_bytes(), before)
        self.assertEqual(output.stat().st_mode & 0o077, 0)

    def test_qmp_reader_uses_only_negotiation_and_allocation_queries(self):
        from unittest.mock import MagicMock
        sockets, streams = [], []
        for vid, name, maximum in ((103, 'Codex-cli', 4096), (201, 'tailscale', 2048)):
            self.put(f'etc/pve/qemu-server/{vid}.conf', f'name: {name}\nmemory: {maximum}\n')
            stream = MagicMock()
            stream.readline.side_effect = [b'{"QMP":{}}\n', b'{"id":"sizing-read","return":{}}\n',
                json.dumps({'id': 'sizing-read', 'return': {'actual': maximum * sizing.MIB}}).encode() + b'\n']
            sock = MagicMock(); sock.__enter__.return_value = sock; sock.makefile.return_value = stream
            sockets.append(sock); streams.append(stream)
        with patch.object(self.ops.socket, 'socket', side_effect=sockets):
            self.assertEqual(self.ops.balloon_growth(self.root), 0)
        for stream in streams:
            self.assertEqual([json.loads(c.args[0])['execute'] for c in stream.write.call_args_list],
                             ['qmp_capabilities', 'query-balloon'])


if __name__ == '__main__': unittest.main()
