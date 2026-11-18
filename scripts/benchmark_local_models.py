import argparse
import json
from pathlib import Path
import sys
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from memory_manager.phase2.benchmark import CASES, run
from memory_manager.phase2.local_model import LocalModel, ModelConfig, PrivateHTTP

parser = argparse.ArgumentParser()
group = parser.add_mutually_exclusive_group(required=True)
group.add_argument('--simulate', action='store_true')
group.add_argument('--live-config')
parser.add_argument('--output', default='docs/JARVIS_2_PHASE2_BENCHMARK.json')
args = parser.parse_args()
if args.simulate:
    class Simulator:
        config = SimpleNamespace(context_tokens=8192)
        def generate(self, messages, schema, **_):
            expected = next(expected for _, prompt, _, expected in CASES if prompt == messages[-1]['content'])
            from memory_manager.phase2.validation import validate
            return validate(expected, schema), {}
    result = run(Simulator(), simulated=True)
else:
    config = json.loads(Path(args.live_config).read_text())
    telemetry_path = Path(config['telemetry_file'])
    http = PrivateHTTP(config['base_url'])
    model = LocalModel(ModelConfig(**config['model']), http, lambda: json.loads(telemetry_path.read_text()))
    result = run(model)
Path(args.output).write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
print(json.dumps({'mode': result['mode'], 'passed': result['passed'], 'gpu_benchmark_performed': result['gpu_benchmark_performed']}))
sys.exit(0 if result['passed'] else 1)
