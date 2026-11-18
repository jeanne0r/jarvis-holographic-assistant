"""Build reviewed source archives locally; never connect to or install on Windows."""
import argparse
import hashlib
import io
import json
from pathlib import Path, PurePosixPath, PureWindowsPath
import subprocess
import tarfile

ROOT = Path(__file__).resolve().parent.parent
PIN = '4959268e312a21a361f248e49030d5f5df3984d5'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    output = Path(args.output).resolve()
    if not output.is_relative_to(ROOT / 'data/phase4') or output == ROOT / 'data/phase4':
        raise SystemExit('New laboratory data/phase4 directory required')
    if subprocess.check_output(['git', 'status', '--porcelain', '--', 'memory_manager', 'ops', 'scripts'], cwd=ROOT):
        raise SystemExit('Commit reviewed application sources before creating the bundle')
    source = ROOT / 'data/hermes-upstream'
    actual = subprocess.check_output(['git', '-C', str(source), 'rev-parse', 'HEAD'], text=True).strip()
    if actual != PIN: raise SystemExit('Pinned upstream checkout required')
    output.mkdir(parents=True, mode=0o700, exist_ok=False)
    source_data = subprocess.check_output(['git', '-C', str(source), 'archive', '--format=tar.gz', '--prefix=hermes-agent/', PIN])
    manifest = {'commit': PIN, 'files': []}
    with tarfile.open(fileobj=io.BytesIO(source_data), mode='r:gz') as archive:
        for member in archive:
            p = PurePosixPath(member.name)
            if member.isdir(): continue
            if not member.isfile() or p.is_absolute() or '..' in p.parts:
                raise SystemExit('Archive requires review: links or nonregular paths')
            manifest['files'].append({'path': str(p.relative_to('hermes-agent')),
                                      'sha256': hashlib.sha256(archive.extractfile(member).read()).hexdigest()})
    windows_paths = [PureWindowsPath('C:/JarvisHermesLab/hermes-agent') / r['path'] for r in manifest['files']]
    if (len({str(p).casefold() for p in windows_paths}) != len(windows_paths)
            or any(PureWindowsPath(part).is_reserved() or ':' in part or part.endswith(('.', ' '))
                   for r in manifest['files'] for part in PurePosixPath(r['path']).parts)):
        raise SystemExit('Windows path collision or reserved name: review required')
    (output / 'hermes-source.tar.gz').write_bytes(source_data)
    (output / 'source-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    app = subprocess.check_output(['git', 'archive', '--format=tar.gz', '--prefix=app/', commit, 'memory_manager', 'ops'], cwd=ROOT)
    (output / 'jarvis-adapter.tar.gz').write_bytes(app)
    receipt = {'hermes_commit': PIN, 'application_commit': commit, 'source_files': len(manifest['files']),
               'maximum_windows_source_path_characters': max(len(str(p)) for p in windows_paths),
               'files': {p.name: {'bytes': p.stat().st_size, 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()}
                         for p in output.iterdir() if p.is_file()}, 'windows_modified': False}
    (output / 'bundle-receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps(receipt))


if __name__ == '__main__': main()
