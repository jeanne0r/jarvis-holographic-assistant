"""Publication check. Prints filenames/rules only, never matching secret values."""
import pathlib,re,subprocess,sys
root=pathlib.Path(__file__).resolve().parent.parent
try:files=subprocess.check_output(['git','ls-files','--cached'],cwd=root,text=True).splitlines()
except subprocess.CalledProcessError:raise SystemExit('Initialize and stage the clean release repository first.')
rules={
 'private key':r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----',
 'Google key':r'AIza[0-9A-Za-z_-]{30,}',
 'GitHub token':r'\b(?:gh[pousr]_[A-Za-z0-9]{25,}|github_pat_[A-Za-z0-9_]{40,})',
 'OpenAI token':r'\bsk-(?:proj-)?[A-Za-z0-9_-]{25,}',
 'credential URL':r'https?://[^\s/<>"\']+:[^\s/@<>"\']+@',
 'JWT':r'\beyJ[A-Za-z0-9_-]{15,}\.[A-Za-z0-9_-]{15,}\.[A-Za-z0-9_-]{15,}',
}
issues=[]
for rel in files:
 p=root/rel
 if rel.startswith(('data/','memory/','.venv/','node_modules/')) or p.name in ['.env','auth.json','application_default_credentials.json'] or p.suffix in ['.sqlite','.db','.key','.pem','.p12']:issues.append((rel,'forbidden runtime or credential file'))
 if not p.is_file():continue
 try:text=p.read_text()
 except UnicodeDecodeError:continue
 for label,pattern in rules.items():
  if re.search(pattern,text):issues.append((rel,label))
for file,label in issues:print(f'BLOCKED {file}: {label}')
print(f'Publication scan: {len(files)} tracked files, {len(issues)} findings. Pattern scanning cannot prove the absence of every secret.')
sys.exit(bool(issues))
