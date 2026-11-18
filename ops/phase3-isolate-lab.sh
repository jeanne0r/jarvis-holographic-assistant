#!/usr/bin/env bash
# New laboratory VM only; apply after dependencies and before any agent.
set -eu
[ "$(hostname -s)" = jarvis-lab ]
id hermeslab >/dev/null
cd /home/user/workspace/jarvis-2-memory
test -x data/phase3/install/venv/bin/hermes
sudo -n chmod 751 /home/user
sudo -n chgrp -R hermeslab memory_manager ops data/hermes-upstream data/phase3/install
sudo -n chmod -R g+rX,g-w,o-rwx memory_manager ops data/hermes-upstream data/phase3/install
sudo -n chown hermeslab:hermeslab data/phase3/prepared
sudo -n chmod 750 data/phase3/prepared
sudo -n chown hermeslab:hermeslab data/phase3/prepared/memory.token data/phase3/prepared/model.token data/phase3/prepared/hermes.token data/phase3/prepared/config.yaml data/phase3/prepared/config-skill.yaml
sudo -n install -d -m 700 -o hermeslab -g hermeslab data/phase3/prepared/hermes-home data/phase3/prepared/hermes-home-skill
if sudo -n nft list table inet jarvis_phase3 >/dev/null 2>&1; then
  echo 'Existing laboratory network table: refuse replacement.' >&2
  exit 1
fi
sudo -n nft -f /dev/stdin <<'NFT'
table inet jarvis_phase3 {
 chain input {
  type filter hook input priority 0; policy drop;
  iifname "lo" accept
  ct state established,related accept
  ip saddr 192.0.2.16 tcp dport 22 accept
 }
 chain output {
  type filter hook output priority 0; policy drop;
  oifname "lo" accept
  ct state established,related accept
 }
 chain forward {
  type filter hook forward priority 0; policy drop;
 }
}
NFT
