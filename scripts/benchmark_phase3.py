import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from memory_manager.phase3.benchmark import run
from memory_manager.phase2.local_model import LocalModel, ModelConfig, PrivateHTTP

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--simulate', action='store_true')
    group.add_argument('--live-config')
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    destination = Path(args.output)
    if destination.exists():
        raise SystemExit('Choose a new report path; existing results are preserved')
    model = None
    if args.live_config:
        cfg = json.loads(Path(args.live_config).read_text())
        model = LocalModel(ModelConfig(**cfg['model']), PrivateHTTP(cfg['base_url']),
                           lambda: json.loads(Path(cfg['telemetry_file']).read_text()))
    result = run(model)
    destination.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({k: result[k] for k in ('simulated', 'completed_cases', 'passed')}))
    sys.exit(0 if result['passed'] else 1)
