"""Offline re-evaluation of immutable real-run evidence, never an inference."""
import hashlib
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from memory_manager.phase3.native_trial import events_from_sse


def evaluate():
    docs = ROOT / 'docs'
    files = ['JARVIS_2_PHASE3_NATIVE_HERMES_REAL_4.json',
             'JARVIS_2_PHASE3_NATIVE_SKILL_REAL_2.json',
             'JARVIS_2_PHASE3_MEMORY_NATIVE_SNAPSHOT_REAL.json',
             'JARVIS_2_PHASE3_HELD_RAM_REAL.json', 'JARVIS_2_PHASE3_NETWORK_REAL.json',
             'JARVIS_2_PHASE3_HERMES_INSTALL_REAL.json']
    proof = {name: json.loads((docs / name).read_text()) for name in files}
    run, skill, memory, ram, network, install = [proof[name] for name in files]
    mission = run['native_hermes']['missions'][0]
    events = events_from_sse(mission['native_events_sse'])
    tools = [e['tool'] for e in events if e.get('event') == 'tool.completed' and not e.get('error')]
    mid = mission['mission_id']
    episodes = [r for rows in memory['mission_experiences'].values() for r in rows]
    history = memory['configuration_history']
    output = mission['native_status']['output']
    usages = [u for u in memory['usage'] if u['mission_id'] == mid]
    checks = {
        'official_pinned_runtime': install['hermes_commit'] == '4959268e312a21a361f248e49030d5f5df3984d5',
        'fast_asynchronous_admission': mission['admission_seconds'] < 1,
        'bridge_and_native_completed': mission['bridge_status']['state'] == mission['native_status']['status'] == 'completed',
        'native_search_and_history': all(any(t.endswith(name) for t in tools) for name in ['jarvis_memory_search', 'jarvis_memory_history']),
        'both_sources_cited': all(ref in output for ref in ['synthetic://doselab/correction', 'synthetic://doselab/old']),
        'current_configuration': history[-1]['content']['capacities_kg'] == [1, 1, 1, 1],
        'old_configuration_preserved': history[0]['content']['capacities_kg'] == [1, 2, 5, 10] and history[0]['effective_status'] == 'superseded',
        'experience_persisted_inferred': bool(episodes) and all(r['status'] == 'inferred' and r['source']['ref'] == 'mission://' + mid for r in episodes),
        'three_real_metered_local_calls': len(usages) == 3 and all(u['state'] == 'settled' and u['actual_remote_micros'] == 0 and u['used_tokens'] > 0 for u in usages),
        'actual_64k_ollama_context': run['configuration']['context_tokens'] == 64000 and any(
            m.get('context_length') == 64000 and m.get('digest') == run['model']['digest']
            for row in run.get('residency_samples', []) for m in row['models']),
        'network_denials_observed': network['passed'] and all(c['blocked'] for c in network['checks']),
        'ram_and_shares_restored': all(c['configuration_exactly_restored'] and c['backup_verified'] for c in ram['guest_configurations_after'].values()),
        'lab_stopped_without_autostart': ram['lab']['status'] == 'stopped' and ram['lab']['onboot'] == 0,
        'no_skill_published': memory['active_skills'] == 0,
    }
    return {
        'evaluation': 'offline analysis of actual native SSE, GPU, ledger and SQLite evidence',
        'sources_sha256': {name: hashlib.sha256((docs / name).read_bytes()).hexdigest() for name in files},
        'native_memory_cycle_passed': all(checks.values()), 'checks': checks,
        'native_tools': tools, 'mission_id': mid,
        'native_input_tokens': mission['native_status']['usage']['input_tokens'],
        'native_output_tokens': mission['native_status']['usage']['output_tokens'],
        'sampled_peak_total_vram_mib': run['sampled_peak_vram_mib'],
        'sampled_peak_power_w': run['sampled_peak_power_w'],
        'sampled_board_energy_wh': run['sampled_board_energy_wh'],
        'native_skill_passed': False, 'candidate_count': len(memory['skills']),
        'native_skill_attempt_error': skill.get('native_hermes', {}).get('error'),
        'phase3_complete': False, 'paid_api_calls': 0,
        'limits': ['Skill mission interrupted by resource-window shutdown; no candidate exists.',
                   'Raw aggregate reports retain failed results, including the former SSE parser false negative.',
                   'Real Qdrant/embeddings integration remains deferred; lookup here is canonical SQLite.',
                   'GPU energy uses sparse board-power samples, not wall-socket consumption.',
                   'No production gateway integration or physical command.']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true', help='Re-evaluate without writing evidence')
    args = parser.parse_args()
    report = evaluate()
    output = ROOT / 'docs/JARVIS_2_PHASE3_NATIVE_VALIDATION_REAL.json'
    if not args.check:
        if output.exists():
            raise SystemExit('Evidence already exists; use --check for read-only re-evaluation')
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(report, ensure_ascii=False, indent=2))
    raise SystemExit(0 if report['native_memory_cycle_passed'] else 1)
