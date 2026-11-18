"""Create an inert synthetic fixture; never install or start Hermes/Ollama."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from memory_manager.phase3.lab import prepare

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--destination', required=True)
    args = parser.parse_args()
    manifest = prepare(args.destination)
    print(json.dumps({'prepared': True, 'synthetic_only': True,
                      'runtime_started': manifest['runtime_started']}))
