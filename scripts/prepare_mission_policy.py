"""Minimal private release delta, all operational flags remain untouched."""
import argparse,hashlib,json,shutil
from pathlib import Path
from .prepare_embedded_panel import ROOT

def prepare(destination,installed=Path('/opt/jarvis-hermes-pilot'),*,source_files=None):
    dest=Path(destination);installed=Path(installed)
    source_files=source_files or ['hermes-mission-policy.mjs','hermes-embedded-api.mjs']
    if len(set(source_files))!=len(source_files) or any(Path(n).is_absolute() or '..' in Path(n).parts for n in source_files):raise ValueError('Explicit local source set required')
    if dest.exists():raise FileExistsError('Never overwrite a release or evidence')
    sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
    known=json.loads((installed/'deployment-files.json').read_text())
    for name,fingerprint in known.items():
        p=installed/name
        if p.is_symlink() or not p.resolve().is_relative_to(installed.resolve()) or sha(p)!=fingerprint:
            raise PermissionError('Installed source drift')
    for name in ['hermes-voice-tools.mjs','hybrid-mission-admission.mjs']:
        if sha(ROOT/name)!=sha(installed/name):raise PermissionError('Dependency needs separate review')
    import re
    for name in source_files:
        for dependency in re.findall(r"from ['\"]([^'\"]+)['\"]",(ROOT/name).read_text()):
            if not dependency.startswith('.'):continue
            relative=str((ROOT/name).parent.joinpath(dependency).resolve().relative_to(ROOT))
            if relative not in source_files and (not (installed/relative).is_file() or sha(ROOT/relative)!=sha(installed/relative)):
                raise PermissionError('Dependency changed: use the complete reviewed SSO source set')
    dest.mkdir(parents=True);release=dest/'release';shutil.copytree(installed,release)
    def write(name,raw):
        target=release/name
        if target.exists():target.chmod(0o600)
        target.write_bytes(raw)
    for name in source_files:write(name,(ROOT/name).read_bytes())
    name='docs/pilot-interactive/manifest.json';manifest=json.loads((release/name).read_text())
    for changed in source_files:manifest['files'][changed]=sha(release/changed)
    write(name,(json.dumps(manifest,indent=2)+'\n').encode())
    known_after={str(p.relative_to(release)):sha(p) for p in sorted(release.rglob('*')) if p.is_file() and p!=release/'deployment-files.json'}
    write('deployment-files.json',(json.dumps(known_after,indent=2)+'\n').encode())
    rows=[]
    for p in sorted(release.rglob('*')):
        if not p.is_file():continue
        name=str(p.relative_to(release));old=installed/name
        if old.exists() and sha(old)==sha(p):continue
        row={'target':str(old),'artifact':'release/'+name,'before_sha256':sha(old) if old.exists() else None,'after_sha256':sha(p)}
        if old.exists():
            saved=dest/'before'/name;saved.parent.mkdir(parents=True,exist_ok=True);saved.write_bytes(old.read_bytes())
            if saved.read_bytes()!=old.read_bytes():raise ValueError('Copy mismatch')
            row['backup']='before/'+name
        rows.append(row)
    if {str(Path(row['target']).relative_to(installed)) for row in rows}!=set(source_files)|{'deployment-files.json','docs/pilot-interactive/manifest.json'}:raise PermissionError('Unexpected release delta')
    report={'lot':'C-policy-only','production_modified':False,'all_flags_unchanged':True,'activation_authorized':False,
        'state_or_credentials_copied':False,'installed_manifest_sha256':sha(installed/'deployment-files.json'),'files':rows}
    (dest/'manifest.json').write_text(json.dumps(report,indent=2)+'\n');return report
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('destination');args=p.parse_args();r=prepare(args.destination)
    print(json.dumps({'prepared':True,'changed_files':len(r['files']),'production_modified':False}))
