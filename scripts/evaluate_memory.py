"""Reproducible local evaluation; synthetic fixtures and mocked network only."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import argparse

ROOT = Path(__file__).resolve().parent.parent
COMMANDS = [
    ['python3', '-m', 'unittest', 'discover', '-s', 'memory_manager/tests', '-v'],
    ['python3', 'test_store.py'],
    ['python3', 'test_spaces.py'],
    ['python3', '-m', 'unittest', 'test_conversations', 'test_voice_memory'],
    ['python3', '-m', 'unittest', 'discover', '-s', 'semantic', '-p', 'test_search.py'],
    ['node', 'test_codex_worker.mjs'],
    ['node', 'test_user_corrections.mjs'],
    ['node', 'test_home_assistant.mjs'],
    ['node', 'test_hybrid_brain.mjs'],
]


def main():
    parser = argparse.ArgumentParser()
    phases = parser.add_mutually_exclusive_group()
    phases.add_argument('--phase2', action='store_true')
    phases.add_argument('--phase3', action='store_true')
    phases.add_argument('--phase4', action='store_true')
    phases.add_argument('--phase5', action='store_true')
    phases.add_argument('--phase5c', action='store_true')
    phases.add_argument('--phase6', action='store_true')
    phases.add_argument('--phase6-integration', action='store_true')
    phases.add_argument('--phase6b', action='store_true')
    args = parser.parse_args()
    if args.phase6b: args.phase6_integration=True
    if args.phase6_integration: args.phase6=True
    if args.phase6: args.phase5c = True  # Include the established offline regressions.
    commands = COMMANDS + ([['python3', '-m', 'unittest', 'memory_manager.phase2.test_integration', '-v'],
                            ['python3', 'scripts/benchmark_local_models.py', '--simulate']] if args.phase2 or args.phase3 or args.phase4 or args.phase5 or args.phase5c else [])
    if args.phase3 or args.phase4 or args.phase5 or args.phase5c:
        commands += [['python3', '-m', 'unittest', 'memory_manager.phase3.test_preparation',
                      'memory_manager.phase3.test_sizing', '-v']]
    if args.phase4 or args.phase5 or args.phase5c:
        commands += [['python3', '-m', 'unittest', 'memory_manager.phase4.test_windows', '-v']]
    if args.phase5 or args.phase5c:
        commands += [['python3', '-m', 'unittest', 'memory_manager.phase5.test_memory', 'memory_manager.phase5.test_qdrant_a1', 'memory_manager.phase5.test_a2_deploy', 'memory_manager.phase5.test_ssh_transport', 'memory_manager.phase5.test_native_lab', '-v'], ['node', 'test_hermes_experimental.mjs']]
    if args.phase5c:
        commands += [['python3','-m','unittest','memory_manager.phase5c.test_preparation','memory_manager.phase5c.test_local_review','memory_manager.phase5c.test_metadata_inventory','-v'], ['node','test_hermes_server_auth.mjs']]
    if args.phase6:
        commands += [['python3','-m','unittest','memory_manager.phase6.test_turn_plan','-v'],['node','test_phase6.mjs']]
    if args.phase6_integration:
        commands += [['node','test_live.mjs'],['node','test_phase6_gateway.mjs'],['node','test_phase6_ui.cjs']]
    if args.phase6b:
        commands += [['node','--experimental-loader','./test_phase6_hybrid_loader.mjs','test_phase6_hybrid.mjs'], ['node','test_phase6_ui.cjs','--hybrid'], ['node','test_speech.mjs']]
    report = {'evaluated_at': datetime.now(timezone.utc).isoformat(), 'data': 'synthetic',
              'real_model_calls': 0, 'production_writes': 0, 'checks': [], 'phase': '6B' if args.phase6b else 6 if args.phase6 else '5C' if args.phase5c else 5 if args.phase5 else 4 if args.phase4 else 3 if args.phase3 else 2 if args.phase2 else 1}
    # Do not pass model/provider credentials to the evaluation processes.
    with tempfile.TemporaryDirectory(prefix='jarvis-2-eval-home-') as home:
        env = {'PATH': os.environ['PATH'], 'HOME': home, 'LANG': 'C.UTF-8', 'PYTHONDONTWRITEBYTECODE': '1'}
        for command in commands:
            result = subprocess.run(command, cwd=ROOT, env=env, text=True, capture_output=True, timeout=60)
            report['checks'].append({'command': command, 'exit_code': result.returncode,
                                     'output': result.stdout + result.stderr})
            print(('PASS ' if result.returncode == 0 else 'FAIL ') + ' '.join(command), flush=True)
    report['passed'] = all(c['exit_code'] == 0 for c in report['checks'])
    output = ROOT / 'docs' / ('JARVIS_2_PHASE6B_TEST_RESULTS.json' if args.phase6b else 'JARVIS_2_PHASE6_INTEGRATION_TEST_RESULTS.json' if args.phase6_integration else 'JARVIS_2_PHASE6_TEST_RESULTS.json' if args.phase6 else 'JARVIS_2_PHASE5C_TEST_RESULTS.json' if args.phase5c else 'JARVIS_2_PHASE5_TEST_RESULTS.json' if args.phase5 else 'JARVIS_2_PHASE4_TEST_RESULTS.json' if args.phase4 else 'JARVIS_2_PHASE3_TEST_RESULTS.json' if args.phase3 else 'JARVIS_2_PHASE2_TEST_RESULTS.json' if args.phase2 else 'JARVIS_2_TEST_RESULTS.json')
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    sys.exit(main())
