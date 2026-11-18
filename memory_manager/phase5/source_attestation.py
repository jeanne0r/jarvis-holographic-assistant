"""Read-only verification of the reviewed Hermes archive; Git is not installed on GAMER."""
import hashlib
import json
from pathlib import Path
import time

PIN = '4959268e312a21a361f248e49030d5f5df3984d5'
MANIFEST_SHA = '5938500e2801bb2157ec04cc14da0fd2fee7d8b693cccdeca94ec4f257ecec0d'


def verify(root, manifest_bytes, *, expected_sha=MANIFEST_SHA, seconds=50, start=0, count=None):
    if hashlib.sha256(manifest_bytes).hexdigest() != expected_sha:
        raise PermissionError('Reviewed manifest fingerprint changed')
    manifest = json.loads(manifest_bytes)
    if manifest.get('commit') != PIN or not manifest.get('files'):
        raise PermissionError('Pinned nonempty archive required')
    root = Path(root).resolve()
    started = time.monotonic()
    rows=manifest['files'][start:] if count is None else manifest['files'][start:start+count]
    for row in rows:
        if time.monotonic() - started >= seconds:
            raise TimeoutError('Source verification deadline reached')
        path = root / row['path']
        if not path.resolve().is_relative_to(root) or path.is_symlink() or not path.is_file():
            raise PermissionError('Source path escaped or missing')
        with path.open('rb') as stream:
            if hashlib.file_digest(stream, 'sha256').hexdigest() != row['sha256']:
                raise PermissionError('Pinned source file changed')
    return {'hermes_commit': PIN, 'manifest_sha256': expected_sha,
            'source_files_verified': len(rows), 'total_files':len(manifest['files']), 'start':start,
            'seconds': round(time.monotonic() - started, 3)}


if __name__ == '__main__':
    print(json.dumps(verify(Path('C:/JarvisHermesLab/hermes-agent'),
                           Path('C:/JarvisHermesLab/source-manifest.json').read_bytes())))
