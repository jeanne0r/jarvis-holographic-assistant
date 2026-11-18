#!/bin/bash
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq ca-certificates curl python3-venv python3-pip
id jarvis-memory >/dev/null 2>&1 || useradd --system --home /var/lib/jarvis-memory --create-home --shell /usr/sbin/nologin jarvis-memory
install -d -o jarvis-memory -g jarvis-memory /var/lib/jarvis-memory/qdrant /var/lib/jarvis-memory/models
python3 - <<'PY'
import hashlib,json,pathlib,tarfile,urllib.request
r=json.load(open('/opt/jarvis-memory/qdrant-release.json'))
p=pathlib.Path('/tmp/qdrant-release.tar.gz');urllib.request.urlretrieve(r['url'],p)
assert hashlib.sha256(p.read_bytes()).hexdigest()==r['digest'].removeprefix('sha256:')
with tarfile.open(p) as t:
 member=next(m for m in t.getmembers() if m.name.removeprefix('./')=='qdrant')
 with t.extractfile(member) as f: pathlib.Path('/usr/local/bin/qdrant').write_bytes(f.read())
pathlib.Path('/usr/local/bin/qdrant').chmod(0o755);p.unlink()
PY
python3 -m venv /opt/jarvis-memory/venv
/opt/jarvis-memory/venv/bin/pip install --no-cache-dir --quiet -r /opt/jarvis-memory/requirements.lock
chown root:jarvis-memory /etc/jarvis-memory.env
chmod 640 /etc/jarvis-memory.env
cat > /opt/jarvis-memory/qdrant.yaml <<'YAML'
log_level: WARN
storage:
  storage_path: /var/lib/jarvis-memory/qdrant
  snapshots_path: /var/lib/jarvis-memory/snapshots
  performance:
    max_search_threads: 2
    max_optimization_threads: 1
service:
  host: 0.0.0.0
  http_port: 6333
  grpc_port: 6334
telemetry_disabled: true
YAML
cat > /etc/systemd/system/jarvis-qdrant.service <<'UNIT'
[Unit]
Description=Jarvis Qdrant semantic index
After=network-online.target
Wants=network-online.target
[Service]
User=jarvis-memory
Group=jarvis-memory
EnvironmentFile=/etc/jarvis-memory.env
WorkingDirectory=/var/lib/jarvis-memory
ExecStart=/usr/local/bin/qdrant --config-path /opt/jarvis-memory/qdrant.yaml
Restart=on-failure
RestartSec=3
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/var/lib/jarvis-memory
UMask=0077
[Install]
WantedBy=multi-user.target
UNIT
cat > /etc/systemd/system/jarvis-embeddings.service <<'UNIT'
[Unit]
Description=Jarvis local multilingual embeddings and search
After=network-online.target jarvis-qdrant.service
Wants=network-online.target jarvis-qdrant.service
[Service]
User=jarvis-memory
Group=jarvis-memory
EnvironmentFile=/etc/jarvis-memory.env
Environment=HF_HUB_DISABLE_TELEMETRY=1
Environment=TOKENIZERS_PARALLELISM=false
Environment=OMP_NUM_THREADS=2
WorkingDirectory=/opt/jarvis-memory
ExecStart=/opt/jarvis-memory/venv/bin/uvicorn service:app --host 0.0.0.0 --port 6335 --no-access-log
Restart=on-failure
RestartSec=3
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/var/lib/jarvis-memory
UMask=0077
[Install]
WantedBy=multi-user.target
UNIT
systemctl daemon-reload
systemctl enable --now jarvis-qdrant.service jarvis-embeddings.service
