#!/bin/bash
# Real install of the simplified supervisor on the ISOLATED dev VM (jarvis-dev) only.
# Windows is simulated by a local dummy interface (198.18.0.96, RFC 2544 benchmark
# range): no packet leaves this VM. Run: sudo bash ops/demand-simple/vm-integration-test.sh
# KEEP=1 leaves the installation in place for inspection.
set -uo pipefail
[ "$(id -u)" = 0 ] || { echo "root required"; exit 2; }
[ "$(hostname)" = jarvis-dev ] || { echo "refusing: dev VM jarvis-dev only"; exit 2; }
REPO=$(cd "$(dirname "$0")/../.." && pwd)
SIM=198.18.0.96
UNIT=jarvis-hermes-supervisor.service
WORK=$(mktemp -d)
PASS=0; FAIL=0
ok()  { echo "  ✅ $*"; PASS=$((PASS+1)); }
ko()  { echo "  ❌ $*"; FAIL=$((FAIL+1)); }
check() { local name=$1; shift; if "$@"; then ok "$name"; else ko "$name"; fi; }
jget() { python3 -c "import json,sys;d=json.load(open('$1'));print(eval(sys.argv[1],{},{'d':d}))" "$2"; }
listen() { systemd-run --quiet --unit="jsim-$1" --property=Type=simple /usr/bin/python3 -m http.server --bind "$2" "$3" >/dev/null; }

cleanup_sim() {
  for u in jsim-queue jsim-gateway jsim-rdp; do systemctl stop "$u" 2>/dev/null; done
  ip link del jsim0 2>/dev/null; ip route del unreachable $SIM/32 2>/dev/null
}
cleanup_all() {
  systemctl stop $UNIT jarvis-hermes-private-boot.service 2>/dev/null; systemctl reset-failed $UNIT jarvis-hermes-private-boot.service 2>/dev/null
  rm -f /run/jsim-coordinator-started
  rm -f /etc/systemd/system/$UNIT /etc/systemd/system/jarvis-hermes-private-boot.service /etc/systemd/system/jarvis-hermes-confinement.service
  systemctl daemon-reload
  nft delete table inet jarvis_hermes_supervisor 2>/dev/null
  rm -rf /opt/jarvis-hermes-supervisor /opt/jarvis-hermes-supervisor.previous /etc/jarvis-hermes-supervisor /var/lib/jarvis-hermes-supervisor
  userdel jarvis-hermes-supervisor 2>/dev/null; groupdel jarvis-hermes-supervisor 2>/dev/null
}
start_once() {  # start, wait for the oneshot-like failure/exit, return journal of this invocation
  local since; since=$(date '+%Y-%m-%d %H:%M:%S'); systemctl reset-failed $UNIT 2>/dev/null
  systemctl start $UNIT 2>/dev/null; sleep 3
  journalctl -u $UNIT --since "$since" --no-pager -o cat > "$WORK/journal.txt"
}

echo "== 0. clean slate + simulated environment"
cleanup_all; cleanup_sim
ip link add jsim0 type dummy && ip addr add $SIM/32 dev jsim0 && ip link set jsim0 up
listen queue 127.0.0.1 8797; listen gateway 127.0.0.1 8788; listen rdp $SIM 3389
sleep 1
# Source = a copy of the repo where ONLY the coordinator is a stub: the real one installs
# /opt/jarvis-hermes-pilot. The real private-boot unit and real start-private-queue.py
# (installed by install.py) run unchanged, with their real pin checks.
SRC=$WORK/src; mkdir "$SRC"
git -C "$REPO" ls-files -z | (cd "$REPO" && xargs -0 cp --parents -t "$SRC")
cat > "$SRC/ops/pilot-network/install-system-pilot.py" <<'EOF'
# TEST STUB coordinator (jarvis-dev only): proves the boot hook reached it after its pins.
from pathlib import Path
def verify_layout(): pass
def supervised_start(): Path('/run/jsim-coordinator-started').write_text('1')
EOF
COORD=$(sha256sum "$SRC/ops/pilot-network/install-system-pilot.py" | cut -d' ' -f1)
install -d -m 750 /etc/jarvis-hermes-supervisor
printf '{"coordinatorSha256": "%s", "egressFileSha256": "old", "egressRulesSha256": "old", "operatorKey": "kept"}\n' "$COORD" > /etc/jarvis-hermes-supervisor/boot.json
chmod 600 /etc/jarvis-hermes-supervisor/boot.json
# Reproduce the failed prod state: old attestation unit + code dir unreadable (CHDIR cause).
printf '[Service]\nType=oneshot\nExecStart=/bin/false\n' > /etc/systemd/system/jarvis-hermes-confinement.service
mkdir -p /opt/jarvis-hermes-supervisor/scripts && echo "# old" > /opt/jarvis-hermes-supervisor/scripts/old.py && chmod -R 0700 /opt/jarvis-hermes-supervisor
systemctl daemon-reload
cat > "$WORK/initial.json" <<EOF
{"enabled": false, "remoteCostChf": 0, "confinementReceipt": "/etc/jarvis-hermes-supervisor/confinement.json",
 "sourceFiles": {"scripts/demand_supervisor.py": "e33e873273eb5e53fb0dca6a10899f70100557a42d7a8e48e44a27642a95379f"}}
EOF

echo "== 1. first install"
python3 -I "$SRC/ops/demand-simple/install.py" --source "$SRC" --windows-host $SIM --initial-config "$WORK/initial.json" > "$WORK/r1.json"
check "install passed"                       [ "$(jget "$WORK/r1.json" "d['passed']")" = True ]
check "verified AS service UID before start" [ "$(jget "$WORK/r1.json" "d['verified_as_service']['source_files']>50")" = True ]
check "not started, not enabled"             [ "$(systemctl is-active $UNIT)" != active -a "$(systemctl is-enabled $UNIT)" = disabled ]
check "old attestation unit removed"         [ ! -e /etc/systemd/system/jarvis-hermes-confinement.service ]
check "previous release kept for rollback"   [ -f /opt/jarvis-hermes-supervisor.previous/scripts/old.py ]
check "code root:group 0750/0640"            [ "$(stat -c %U:%a /opt/jarvis-hermes-supervisor)" = root:750 -a "$(stat -c %a /opt/jarvis-hermes-supervisor/scripts/demand_supervisor.py)" = 640 ]
check "config owned by service, 0600"        [ "$(stat -c %U:%a /etc/jarvis-hermes-supervisor/config.json)" = jarvis-hermes-supervisor:600 ]
H=$(sha256sum "$SRC/scripts/demand_supervisor.py" | cut -d' ' -f1)
check "fingerprint generated (not e33e8732)" [ "$(python3 -c "import json;print(json.load(open('/etc/jarvis-hermes-supervisor/config.json'))['sourceFiles']['scripts/demand_supervisor.py'])")" = "$H" ]
check "enabled left false, receipt key gone" python3 -c "import json,sys;c=json.load(open('/etc/jarvis-hermes-supervisor/config.json'));sys.exit(not(c['enabled'] is False and 'confinementReceipt' not in c))"
check "nft table loaded for the UID"         nft list table inet jarvis_hermes_supervisor
check "boot.json re-pinned to written+loaded rules, other keys kept" python3 - <<EOF
import json,hashlib,sys
b=json.load(open('/etc/jarvis-hermes-supervisor/boot.json'))
sys.exit(not(b['egressFileSha256']==hashlib.sha256(open('/etc/jarvis-hermes-supervisor/egress.nft','rb').read()).hexdigest()
  and len(b['egressRulesSha256'])==64 and b['coordinatorSha256']=='$COORD' and b['operatorKey']=='kept'))
EOF
check "real private-boot unit installed from template" cmp -s "$SRC/ops/demand/jarvis-hermes-private-boot.service.in" /etc/systemd/system/jarvis-hermes-private-boot.service
check "state dirs incl. data/phase4, 0700"   [ "$(stat -c %U:%a /var/lib/jarvis-hermes-supervisor/data/phase4)" = jarvis-hermes-supervisor:700 -a -d /var/lib/jarvis-hermes-supervisor/ssh/hermes ]

echo "== 2. second install is a no-op (idempotent)"
python3 -I "$SRC/ops/demand-simple/install.py" --source "$SRC" --windows-host $SIM > "$WORK/r2.json"
check "changed == []"                        [ "$(jget "$WORK/r2.json" "d['changed']")" = "[]" ]
python3 -I "$SRC/ops/demand-simple/install.py" --source "$SRC" --windows-host $SIM --check > "$WORK/c1.json"
check "--check on clean install: would_change == [], coordinator checked" [ "$(jget "$WORK/c1.json" "(d['would_change'],d['nothing_written'],d['coordinator_checked'])")" = "([], True, True)" ]

echo "== 3. start: self-test passes, then activation gate (enabled=false) stops it"
start_once
check "REAL private-boot passed its pins and reached the coordinator" [ "$(systemctl is-active jarvis-hermes-private-boot.service)" = active -a -f /run/jsim-coordinator-started ]
check "self-test passed (allowed + forbidden)" grep -q '"passed": true' "$WORK/journal.txt"
check "queue connected, windows ssh connected" python3 - "$WORK/journal.txt" <<'EOF'
import json,sys
r=next(json.loads(l) for l in open(sys.argv[1]) if l.startswith('{"checks"'))
c={x['name']+str(x['target']):x['outcome'] for x in r['checks']}
sys.exit(not(c["queue['127.0.0.1', 8797]"]=='connected' and c["windows_ssh['198.18.0.96', 22]"]=='connected'))
EOF
check "forbidden refused: witnesses, gateway 8788, sim RDP 3389, IPv6" python3 - "$WORK/journal.txt" <<'EOF'
import json,sys
r=next(json.loads(l) for l in open(sys.argv[1]) if l.startswith('{"checks"'))
f=[x for x in r['checks'] if x['kind']=='forbidden'];print('   ',[(x['name'],x['target'],x['outcome']) for x in f])
sys.exit(not(all(x['ok'] for x in f) and len(f)>=7))
EOF
check "activation gate held (no execution)"  grep -q 'Approved supervisor activation required' "$WORK/journal.txt"

echo "== 4. NEGATIVE: permissive egress table -> self-test must refuse start"
cp /etc/jarvis-hermes-supervisor/egress.nft "$WORK/good.nft"
printf 'table inet jarvis_hermes_supervisor\ndelete table inet jarvis_hermes_supervisor\ntable inet jarvis_hermes_supervisor {\n chain output {\n  type filter hook output priority 10; policy accept;\n }\n}\n' > /etc/jarvis-hermes-supervisor/egress.nft
start_once
check "start refused by ExecStartPre"        grep -q '"passed": false' "$WORK/journal.txt"
check "executor never reached"               bash -c "! grep -q 'Approved supervisor activation required' $WORK/journal.txt"
check "gateway 8788 reported as reached"     grep -q '"outcome": "connected", "target": \["127.0.0.1", 8788\]' "$WORK/journal.txt"
systemctl stop jarvis-hermes-private-boot.service; S=$(date '+%Y-%m-%d %H:%M:%S'); systemctl start jarvis-hermes-private-boot.service 2>/dev/null
check "private-boot refuses the tampered egress.nft (pinned file sha)" [ "$(systemctl is-active jarvis-hermes-private-boot.service)" = failed ]
check "  ...and the reason is the egress pin" bash -c "journalctl -u jarvis-hermes-private-boot --since '$S' --no-pager -o cat | grep -q 'Pinned dedicated'"
systemctl reset-failed jarvis-hermes-private-boot.service
python3 -I "$SRC/ops/demand-simple/install.py" --source "$SRC" --windows-host $SIM --check > "$WORK/c2.json"
check "--check reports egress.nft, writes nothing" [ "$(jget "$WORK/c2.json" "d['would_change']")" = "['/etc/jarvis-hermes-supervisor/egress.nft']" -a "$(sha256sum < /etc/jarvis-hermes-supervisor/egress.nft)" != "$(sha256sum < "$WORK/good.nft")" ]
python3 -I "$SRC/ops/demand-simple/install.py" --source "$SRC" --windows-host $SIM > "$WORK/r3.json"
check "re-install repairs only egress.nft"   [ "$(jget "$WORK/r3.json" "d['changed']")" = "['/etc/jarvis-hermes-supervisor/egress.nft']" ]

echo "== 5. NEGATIVE: private queue down -> positive control fails"
systemctl stop jsim-queue; start_once
check "start refused (queue)"                grep -q '"name": "queue", "ok": false' "$WORK/journal.txt"
listen queue 127.0.0.1 8797; sleep 1

echo "== 6. NEGATIVE: Windows off -> start allowed, mission mode refused"
# Local unreachable route: the SYN never leaves the VM (no default-route leak).
ip addr del $SIM/32 dev jsim0 && ip route add unreachable $SIM/32
cd /opt/jarvis-hermes-supervisor
U=$(id -u jarvis-hermes-supervisor); G=$(id -g jarvis-hermes-supervisor)
setpriv --reuid $U --regid $G --clear-groups /usr/bin/python3 -B -m scripts.egress_selftest --policy /etc/jarvis-hermes-supervisor/egress-policy.json --mode mission > "$WORK/m.json"; rc=$?
check "mission self-test refuses (rc=$rc)"   [ $rc -ne 0 ]
check "windows outcome is absence, not block" grep -qE '"name": "windows_ssh", "ok": false, "outcome": "(timeout|unreachable)"|"outcome": "(timeout|unreachable)", "target": \["198.18.0.96", 22\]' "$WORK/m.json"
setpriv --reuid $U --regid $G --clear-groups /usr/bin/python3 -B -m scripts.egress_selftest --policy /etc/jarvis-hermes-supervisor/egress-policy.json --mode start > /dev/null; rc=$?
check "start-mode self-test still passes (rc=$rc)" [ $rc -eq 0 ]
cd /; ip route del unreachable $SIM/32; ip addr add $SIM/32 dev jsim0

echo "== 6b. NEGATIVE: coordinator pin mismatch -> refused BEFORE any code swap"
cp /etc/jarvis-hermes-supervisor/boot.json "$WORK/boot.good"
python3 -c "import json;p='/etc/jarvis-hermes-supervisor/boot.json';b=json.load(open(p));b['coordinatorSha256']='0'*64;open(p,'w').write(json.dumps(b))"
echo "# drift" >> "$SRC/scripts/egress_selftest.py"
T0=$(find /opt/jarvis-hermes-supervisor -type f -exec sha256sum {} + | sort | sha256sum)
python3 -I "$SRC/ops/demand-simple/install.py" --source "$SRC" --windows-host $SIM > "$WORK/r5.json"; rc=$?
T1=$(find /opt/jarvis-hermes-supervisor -type f -exec sha256sum {} + | sort | sha256sum)
check "refused at release (rc=$rc), coordinatorSha256 named, /opt untouched" [ $rc -eq 2 -a "$(jget "$WORK/r5.json" "d['step']")" = release -a "$T0" = "$T1" ] 
grep -q coordinatorSha256 "$WORK/r5.json" || ko "error names coordinatorSha256"
sed -i '$ d' "$SRC/scripts/egress_selftest.py"; cp "$WORK/boot.good" /etc/jarvis-hermes-supervisor/boot.json

echo "== 7. NEGATIVE: installer refuses while the service runs"
mkdir -p /run/systemd/system/$UNIT.d && printf '[Service]\nExecStartPre=\nExecStart=\nExecStart=/bin/sleep 30\n' > /run/systemd/system/$UNIT.d/test-active.conf
systemctl daemon-reload; systemctl start $UNIT; sleep 1
python3 -I "$SRC/ops/demand-simple/install.py" --source "$SRC" --windows-host $SIM > "$WORK/r4.json"; rc=$?
check "refused, rc=$rc, nothing changed"     [ $rc -eq 2 -a "$(jget "$WORK/r4.json" "d['changed']")" = "[]" ]
systemctl stop $UNIT 2>/dev/null; rm -rf /run/systemd/system/$UNIT.d; systemctl daemon-reload

echo "== result: $PASS ok, $FAIL failed"
cleanup_sim
[ "${KEEP:-0}" = 1 ] || cleanup_all
rm -rf "$WORK"
[ $FAIL -eq 0 ]
