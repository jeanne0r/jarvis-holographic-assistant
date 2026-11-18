#!/bin/bash
# Phased production run of the simplified supervisor installer, executed BY THE OPERATOR
# on the production host. Every phase stops; nothing chains implicitly.
#
#   sudo bash prod-run.sh pre        read-only: pins, units, config, verdict
#   sudo bash prod-run.sh check      read-only: install.py --check (what WOULD change)
#   sudo bash prod-run.sh install    backup -> pre -> check -> confirm -> install (no start) -> idempotence
#   sudo bash prod-run.sh dry-start  enabled=false, start once: private-boot + egress self-test, NO mission
#   sudo bash prod-run.sh arm        arm the PRIVATE service (executionEnabled + runtime identities): accord 3
#   sudo bash prod-run.sh activate   enabled=true, start: the supervisor takes the next queued demand
#   sudo bash prod-run.sh disarm     restore the private service config backed up by `arm`
#   sudo bash prod-run.sh private-update  apply the latest reviewed private-release step (see STEPS in private_update.py)
#   sudo bash prod-run.sh ui-update       apply the latest Hermes UI step (gateway hermes-embedded.js/.css, see frontend_update.py)
#   sudo bash prod-run.sh ui-revert       undo the latest applied Hermes UI step
#   sudo bash prod-run.sh route-backend   Jarvis classifier route 3 (hybrid-brain.mjs), after ui-update step 4; gateway restart separate
#   sudo bash prod-run.sh route-revert    restore the previous hybrid-brain.mjs (then restart the gateway)
#   sudo bash prod-run.sh private-revert  restore the private-release files backed up by private-update
#   sudo bash prod-run.sh real-reset      DEFINITIVE removal of the DoseLab memory (fresh database), see reset_memory.py
#   sudo bash prod-run.sh sources-config  HA / InfluxDB read-only settings, tokens typed hidden -> sources.json (0600)
#   sudo bash prod-run.sh sources-network allow the private service to reach exactly those IPs (drop-in), restart it
#   sudo bash prod-run.sh windows-mcp     supervisor side of the new MCP proxy files (copies, sourceFiles, bindings)
#   sudo bash prod-run.sh windows-mcp-revert  undo the latest windows-mcp step
#   sudo bash prod-run.sh reconcile [MID]     list uncertain missions; with MID, close it as failed (never replayed)
#   sudo bash prod-run.sh rollback   revert UI, Windows-MCP pins, network, private updates, disarm, then restore `install`
#
# Env: SRC (default: this checkout), WIN (Windows host), HA (Home Assistant host),
#      TOKENS (runtime token dir), JARVIS_PROD_HOST (expected hostname),
#      YES=1 skips typed confirmations (tests only).
set -uo pipefail
PHASE=${1:-}
SRC=${SRC:-$(cd "$(dirname "$0")/../.." && pwd)}
WIN=${WIN:-192.0.2.96}
HA=${HA:-192.0.2.215}
TOKENS=${TOKENS:-/home/user/workspace/jarvis-2-memory/data/phase3/windows-20261114}
EXPECT_HOST=${JARVIS_PROD_HOST:-codex-cli}
NAME=jarvis-hermes-supervisor
UNIT=$NAME.service
BOOT_UNIT=jarvis-hermes-private-boot.service
OLD_UNIT=jarvis-hermes-confinement.service
C=/etc/$NAME
OPT=/opt/$NAME
BK_ROOT=/var/backups/jarvis-hermes
LAST=$BK_ROOT/simple-LAST

die() { echo "⛔ $*" >&2; exit 2; }
say() { echo; echo "== $*"; }
confirm() {  # confirm WORD "what happens"
  [ "${YES:-0}" = 1 ] && return 0
  echo; echo "$2"; read -r -p "Taper $1 pour continuer (autre chose = arrêt) : " a
  [ "$a" = "$1" ] || die "arrêt demandé, rien de plus n'a été fait"
}
[ "$(id -u)" = 0 ] || die "root requis (sudo)"
[ "$(hostname)" = "$EXPECT_HOST" ] || die "hôte $(hostname) ≠ $EXPECT_HOST (JARVIS_PROD_HOST)"
[ -f "$SRC/ops/demand-simple/install.py" ] || die "source introuvable : $SRC"
INSTALL=(python3 -I "$SRC/ops/demand-simple/install.py" --source "$SRC" --windows-host "$WIN" --forbid "$HA:8123")
active() { systemctl is-active "$UNIT" 2>/dev/null; }
set_enabled() {  # rewrite in place: owner/mode kept, installer's exact format
  python3 -I -c "import json,sys;p='$C/config.json';c=json.load(open(p));c['enabled']=(sys.argv[1]=='true');open(p,'w').write(json.dumps(c,indent=1,sort_keys=True)+'\n')" "$1"
  python3 -I -c "import json;print('   enabled =',json.load(open('$C/config.json'))['enabled'])"
  echo "   $(stat -c '%U %a' "$C/config.json") (attendu : $NAME 600)"
}
journal_since() { journalctl -u "$1" --since "$2" --no-pager -o cat; }

pre() {
  say "PRE (lecture seule) — source $(git -c safe.directory='*' -C "$SRC" rev-parse --short HEAD 2>/dev/null || echo '?')"
  SRC="$SRC" python3 -I - <<'EOF'
import hashlib, json, os, subprocess, sys
src, C, OPT = os.environ['SRC'], '/etc/jarvis-hermes-supervisor', '/opt/jarvis-hermes-supervisor'
def sha(p):
    try: return hashlib.sha256(open(p, 'rb').read()).hexdigest()
    except FileNotFoundError: return None
def load(p):
    try: return json.load(open(p))
    except FileNotFoundError: return None
boot, cfg = load(C + '/boot.json'), load(C + '/config.json')
problems = []
if boot is None: problems.append('boot.json absent')
if cfg is None: problems.append('config.json absent')
boot, cfg = boot or {}, cfg or {}
coord = 'ops/pilot-network/install-system-pilot.py'
r = {'coordinator': {'pin_boot_json': boot.get('coordinatorSha256'), 'installed_opt': sha(OPT + '/' + coord), 'release_source': sha(src + '/' + coord)},
     'egress_file': {'pin_boot_json': boot.get('egressFileSha256'), 'installed': sha(C + '/egress.nft')},
     'boot_keys': sorted(boot),
     'config': {k: cfg.get(k) for k in ['enabled', 'remoteCostChf', 'bindingsFile', 'bindingsSha256']} | {'keys': sorted(cfg)},
     'bindings_file_sha': sha(cfg.get('bindingsFile') or '/nonexistent')}
if r['coordinator']['pin_boot_json'] != r['coordinator']['release_source']: problems.append('coordinatorSha256 ≠ coordinateur de la release : installation refusée')
if cfg.get('bindingsFile') and r['bindings_file_sha'] != cfg.get('bindingsSha256'): problems.append('windows-bindings.json ≠ bindingsSha256')
if not cfg.get('bindingsFile'): problems.append('bindingsFile absent de la config')
units = subprocess.run(['systemctl', 'show', 'jarvis-hermes-supervisor', 'jarvis-hermes-private-boot', 'jarvis-hermes-confinement',
                        'jarvis-hermes-pilot-system', '-p', 'Id', '-p', 'ActiveState', '-p', 'Result', '-p', 'UnitFileState'],
                       capture_output=True, text=True).stdout.strip().split('\n\n')
r['units'] = [dict(l.split('=', 1) for l in u.splitlines() if '=' in l) for u in units]
refs = subprocess.run(['grep', '-rl', OPT, '/etc/systemd/system'], capture_output=True, text=True).stdout.split()
r['units_using_opt'] = refs
known = {'/etc/systemd/system/' + n for n in ['jarvis-hermes-supervisor.service', 'jarvis-hermes-private-boot.service', 'jarvis-hermes-confinement.service']}
if set(refs) - known: problems.append('autres unités dépendant de /opt : ' + ', '.join(sorted(set(refs) - known)))
r['problems'] = problems; r['verdict'] = 'OK' if not problems else 'STOP'
print(json.dumps(r, indent=1, ensure_ascii=False))
sys.exit(0 if not problems else 1)
EOF
}

check() {
  say "CHECK (lecture seule) — install.py --check"
  "${INSTALL[@]}" --check
}

install_phase() {
  [ "$(active)" = active ] && die "$UNIT est actif : une mission peut tenir un lease. L'arrêter délibérément d'abord."
  pre || die "PRE en échec, rien n'a été modifié"
  check > /tmp/.jarvis-check.$$ || { cat /tmp/.jarvis-check.$$; rm -f /tmp/.jarvis-check.$$; die "CHECK en échec, rien n'a été modifié"; }
  cat /tmp/.jarvis-check.$$
  confirm INSTALL "Prochaine étape : sauvegarde complète, puis installation SANS démarrage (code /opt, config, egress.nft, boot.json, unités)."
  B=$BK_ROOT/simple-$(date -u +%Y%m%dT%H%M%SZ)
  install -d -m 700 "$BK_ROOT" "$B" && mv /tmp/.jarvis-check.$$ "$B/check.json"
  say "SAUVEGARDE → $B"
  cp -a "$C" "$B/etc" || die "sauvegarde /etc échouée, rien d'installé"
  for u in "$UNIT" "$BOOT_UNIT" "$OLD_UNIT"; do
    if [ -e "/etc/systemd/system/$u" ]; then cp -a "/etc/systemd/system/$u" "$B/"; else echo "$u" >> "$B/units-absent.txt"; fi
  done
  if [ -d "$OPT" ]; then tar -C /opt -cpf "$B/opt.tar" "$NAME" || die "sauvegarde /opt échouée, rien d'installé"; fi
  nft list table inet jarvis_hermes_supervisor > "$B/nft-table.txt" 2>/dev/null || echo absent > "$B/nft-table.txt"
  echo "$B" > "$LAST"
  say "INSTALL (sans démarrage)"
  "${INSTALL[@]}" > "$B/install.json"; rc=$?; cat "$B/install.json"
  [ $rc -eq 0 ] || die "installation refusée (voir ci-dessus). Retour arrière : sudo bash $0 rollback"
  say "IDEMPOTENCE (2e passage)"
  "${INSTALL[@]}" > "$B/install2.json"; cat "$B/install2.json" | python3 -I -c "import json,sys;d=json.load(sys.stdin);print('   changed =',d['changed']);sys.exit(d['changed']!=[])" \
    || die "2e passage non vide : à analyser avant tout démarrage"
  echo; echo "✅ Installé, non démarré. Suite : sudo bash $0 dry-start"
}

dry_start() {
  B=$(cat "$LAST" 2>/dev/null) || die "aucune installation enregistrée ($LAST)"
  [ "$(active)" = active ] && die "$UNIT déjà actif"
  confirm DEMARRER "enabled=false puis un démarrage : private-boot (peut démarrer la file privée sans modèle), table nft, test réseau. Aucune mission."
  [ -f "$B/enabled.before" ] || python3 -I -c "import json;print(json.load(open('$C/config.json'))['enabled'])" > "$B/enabled.before"
  say "enabled → false"; set_enabled false
  S=$(date '+%Y-%m-%d %H:%M:%S'); systemctl reset-failed "$UNIT" "$BOOT_UNIT" 2>/dev/null
  systemctl start "$UNIT" 2>/dev/null; sleep 6
  journal_since "$BOOT_UNIT" "$S" > "$B/dry-boot.txt"; journal_since "$UNIT" "$S" > "$B/dry-supervisor.txt"
  say "journal private-boot"; tail -5 "$B/dry-boot.txt"
  say "journal superviseur"; tail -8 "$B/dry-supervisor.txt"
  ok=1
  [ "$(systemctl is-active "$BOOT_UNIT")" = active ] && echo "  ✅ private-boot actif" || { echo "  ❌ private-boot non actif"; ok=0; }
  grep -q '"passed": true' "$B/dry-supervisor.txt" && echo "  ✅ test réseau passé (autorisé + interdit)" || { echo "  ❌ test réseau non passé"; ok=0; }
  grep -q 'Approved supervisor activation required' "$B/dry-supervisor.txt" && echo "  ✅ arrêt sur la garde d'activation (aucune mission)" || { echo "  ❌ garde d'activation non observée"; ok=0; }
  [ "$(active)" = active ] && { echo "  ❌ superviseur encore actif : arrêt"; systemctl stop "$UNIT"; ok=0; }
  [ $ok = 1 ] && touch "$B/dry-start.ok" && echo && echo "✅ Chaîne prouvée sans mission. Activation (décision opérateur) : sudo bash $0 activate" \
    || die "démarrage à vide incomplet : ne pas activer. Retour arrière possible : sudo bash $0 rollback"
}

ARM=(python3 -I "$SRC/ops/demand-simple/arm.py" --tokens-dir "$TOKENS")
arm_phase() {
  B=$(cat "$LAST" 2>/dev/null) || die "aucune installation enregistrée ($LAST)"
  [ -f "$B/dry-start.ok" ] || die "démarrage à vide non validé : lancer dry-start d'abord"
  say "ARM — contrôle (lecture seule)"
  "${ARM[@]}" --check || die "armement refusé : rien n'a été modifié"
  confirm ARMER "Armement du service privé : executionEnabled=true + 4 identités runtime (jetons jamais affichés). Superviseur arrêté s'il tourne (aucun lease, vérifié), config privée sauvegardée dans $B, service privé redémarré par private-boot (interface Jarvis brièvement indisponible). Le superviseur reste ARRÊTÉ ensuite."
  say "ARM"
  "${ARM[@]}" --apply --backup "$B" | tee "$B/arm.json"; rc=${PIPESTATUS[0]}
  [ "$rc" = 0 ] || die "armement en échec (config d'origine restaurée automatiquement si le redémarrage a échoué). Voir ci-dessus."
  echo; echo "✅ Service privé armé, superviseur arrêté. Démarrage (décision opérateur) : sudo bash $0 activate"
}

disarm_phase() {
  B=$(cat "$LAST" 2>/dev/null) || die "aucune sauvegarde enregistrée"
  [ -f "$B/pilot-config.json" ] || die "aucun armement enregistré dans $B"
  confirm DESARMER "Superviseur arrêté (si aucun lease), config privée d'avant l'armement restaurée, service privé redémarré par private-boot."
  "${ARM[@]}" --disarm --backup "$B" | tee "$B/disarm.json"; [ "${PIPESTATUS[0]}" = 0 ] || die "désarmement incomplet : voir ci-dessus"
  mv "$B/pilot-config.json" "$B/pilot-config.disarmed-$(date -u +%H%M%S).json"
  echo "✅ Désarmé (executionEnabled=false)."
}

UPD=(python3 -I "$SRC/ops/demand-simple/private_update.py" --source "$SRC")
private_update_phase() {
  B=$(cat "$LAST" 2>/dev/null) || die "aucune installation enregistrée ($LAST)"
  say "PRIVATE-UPDATE — contrôle (lecture seule, test d'import du candidat)"
  "${UPD[@]}" --check || die "mise à jour refusée : rien n'a été modifié"
  confirm METTRE-A-JOUR "Remplacement de ces fichiers seuls dans /opt/jarvis-hermes-pilot (+ leurs entrées de deployment-files.json), sauvegarde dans $B (sous-dossier de l'étape, voir \"step\"), superviseur arrêté s'il tourne (aucun lease), service privé redémarré par private-boot. Restauration automatique en cas d'échec."
  "${UPD[@]}" --apply --backup "$B" | tee "$B/private-update-$(date -u +%Y%m%dT%H%M%SZ).json"; [ "${PIPESTATUS[0]}" = 0 ] || die "mise à jour en échec (fichiers précédents restaurés automatiquement). Voir ci-dessus."
  echo; echo "✅ Service privé mis à jour, superviseur arrêté. Démarrage : sudo bash $0 activate"
}

private_revert_phase() {
  B=$(cat "$LAST" 2>/dev/null) || die "aucune sauvegarde enregistrée"
  P=$("${UPD[@]}" --pending --backup "$B") || die "lecture des mises à jour appliquées impossible"
  [ -n "$P" ] || die "aucune mise à jour privée enregistrée dans $B"
  confirm RESTAURER-PRIVE "Annulation de la DERNIÈRE mise à jour du service privé (${P%% *}), redémarrage par private-boot. Encore appliquées : $P"
  "${UPD[@]}" --revert --backup "$B" | tee "$B/private-revert-$(date -u +%Y%m%dT%H%M%SZ).json"; [ "${PIPESTATUS[0]}" = 0 ] || die "restauration incomplète : voir ci-dessus"
  echo "✅ Mise à jour ${P%% *} annulée. Restant appliquées : $("${UPD[@]}" --pending --backup "$B")"
}

FUP=(python3 -I "$SRC/ops/demand-simple/frontend_update.py")
ui_update_phase() {
  B=$(cat "$LAST" 2>/dev/null) || die "aucune installation enregistrée ($LAST)"
  say "UI-UPDATE — contrôle (lecture seule)"
  "${FUP[@]}" --check || die "mise à jour de l'interface refusée : rien n'a été modifié"
  confirm METTRE-A-JOUR-UI "Remplacement des fichiers listés ci-dessus dans /home/user/gateway/public/jarvis (même propriétaire, 0644), sauvegarde dans $B (sous-dossier de l'étape), vérification des fichiers servis en HTTPS. Pas de redémarrage de la gateway, index.html inchangé. Restauration automatique si un fichier servi ne correspond pas."
  "${FUP[@]}" --apply --backup "$B" | tee "$B/frontend-update-$(date -u +%Y%m%dT%H%M%SZ).json"; [ "${PIPESTATUS[0]}" = 0 ] || die "mise à jour de l'interface en échec (fichier précédent restauré). Voir ci-dessus."
  echo; echo "✅ Interface mise à jour. Recharger la page sans cache (Ctrl+Maj+R)."
}

ui_revert_phase() {
  B=$(cat "$LAST" 2>/dev/null) || die "aucune sauvegarde enregistrée"
  P=$("${FUP[@]}" --pending --backup "$B") || die "lecture des mises à jour de l'interface impossible"
  [ -n "$P" ] || die "aucune mise à jour de l'interface enregistrée dans $B"
  confirm RESTAURER-UI "Annulation de la DERNIÈRE mise à jour de l'interface (${P%% *}). Encore appliquées : $P"
  "${FUP[@]}" --revert --backup "$B" | tee "$B/frontend-revert-$(date -u +%Y%m%dT%H%M%SZ).json"; [ "${PIPESTATUS[0]}" = 0 ] || die "restauration de l'interface incomplète : voir ci-dessus"
  echo "✅ Étape ${P%% *} annulée. Restant appliquées : $("${FUP[@]}" --pending --backup "$B")"
}

ROUTE=(python3 -I "$SRC/ops/demand-simple/route_update.py")
route_backend_phase() {
  B=$(cat "$LAST" 2>/dev/null) || die "aucune installation enregistrée ($LAST)"
  say "ROUTE-BACKEND — contrôle (lecture seule)"
  "${ROUTE[@]}" --check || die "aiguillage refusé : rien n'a été modifié"
  confirm AIGUILLER "Remplacement de /home/user/workspace/jarvis/hybrid-brain.mjs (seul fichier ; même propriétaire et mode), sauvegarde dans $B/route-update. Refusé tant que l'interface (frontend-update-4) n'est pas servie. Effet APRÈS redémarrage de la gateway : les analyses d'historique sont confiées à Hermes."
  "${ROUTE[@]}" --apply --backup "$B" | tee "$B/route-update-$(date -u +%Y%m%dT%H%M%SZ).json"; [ "${PIPESTATUS[0]}" = 0 ] || die "aiguillage en échec : voir ci-dessus"
  echo; echo "✅ Fichier en place. Redémarre maintenant la gateway (elle charge l'aiguilleur au démarrage)."
}

route_revert_phase() {
  B=$(cat "$LAST" 2>/dev/null) || die "aucune sauvegarde enregistrée"
  [ -d "$B/route-update" ] || { echo "   (aucun aiguillage appliqué)"; return 0; }
  confirm RESTAURER-AIGUILLAGE "Retour de hybrid-brain.mjs d'avant l'aiguillage Hermes (puis redémarrer la gateway)."
  "${ROUTE[@]}" --revert --backup "$B" || die "restauration de l'aiguillage impossible : voir ci-dessus"
  echo "✅ Aiguillage d'origine restauré. Redémarre la gateway."
}

PY_ARM='import importlib.util,sys;s=importlib.util.spec_from_file_location("a",sys.argv[1]);a=importlib.util.module_from_spec(s);s.loader.exec_module(a);r=a.Arm()'
stop_private() {   # supervisor only if idle (no lease), then the private service
  python3 -I -c "$PY_ARM;r._stop_supervisor_if_idle();r.ctl('stop',a.PILOT);print('   superviseur :',r.state(a.SUPERVISOR),'| service privé :',r.state(a.PILOT))" "$SRC/ops/demand-simple/arm.py" \
    || die "arrêt impossible (lease en cours ?) : rien n'a été modifié"
}
SRCS=(python3 -I "$SRC/ops/demand-simple/sources_setup.py")
RESET=(python3 -I "$SRC/ops/demand-simple/reset_memory.py")
BIND=(python3 -I "$SRC/ops/demand-simple/bindings_update.py" --source "$SRC")

real_reset_phase() {
  B=$(cat "$LAST" 2>/dev/null) || die "aucune installation enregistrée ($LAST)"
  [ -n "$("${UPD[@]}" --pending --backup "$B" | grep -w private-update-4)" ] || die "appliquer d'abord private-update (étape 4, sources réelles)"  # 5 = InfluxDB 3
  say "REAL-RESET — contrôle (lecture seule)"
  "${RESET[@]}" --check --before-stop | tee "$B/real-reset-check.json"; [ "${PIPESTATUS[0]}" = 0 ] || die "contrôle refusé : rien n'a été modifié"
  confirm SUPPRIMER-DOSELAB "IRRÉVERSIBLE : la mémoire DoseLab (enregistrements, missions de test, reçus, file) est remplacée par une base vide de même schéma ; les copies du même dossier sont supprimées. Les copies listées ailleurs ne sont PAS supprimées. Superviseur (si aucun lease) et service privé arrêtés pendant l'opération, service privé redémarré ensuite."
  stop_private
  "${RESET[@]}" --apply --confirm SUPPRIMER-DOSELAB | tee "$B/real-reset.json"; [ "${PIPESTATUS[0]}" = 0 ] || die "suppression refusée : voir ci-dessus (service privé arrêté ; relancer : sudo bash $0 sources-network ou private-boot)"
  "${SRCS[@]}" --restart || die "redémarrage du service privé en échec : voir journalctl -u jarvis-hermes-private-boot"
  echo; echo "✅ DoseLab supprimé, service privé redémarré sur une mémoire vide."
}

sources_config_phase() {
  say "SOURCES-CONFIG — saisie (jetons masqués, jamais affichés)"
  echo "   HA : utilisateur dédié NON-admin + jeton longue durée.  InfluxDB 3 Core : jeton dédié (admin, seul type disponible ;"
  echo "   Hermes ne l'utilise qu'en lecture : GET /api/v3/query_influxql, requête construite par la VM103)."
  "${SRCS[@]}" --config || die "configuration refusée : sources.json inchangé"
  say "test de lecture (depuis l'hôte, comptes seulement)"
  "${SRCS[@]}" --test || echo "⚠️ test en échec : vérifier URL/jetons, puis relancer cette phase"
  echo; echo "Suite : sudo bash $0 sources-network"
}

sources_network_phase() {
  B=$(cat "$LAST" 2>/dev/null) || die "aucune installation enregistrée ($LAST)"
  confirm OUVRIR "Ajout d'un drop-in systemd au service privé : IPAddressAllow= les seules IP de HA et d'InfluxDB de sources.json (le fichier d'unité n'est pas modifié). Superviseur (si aucun lease) et service privé redémarré par private-boot."
  "${SRCS[@]}" --network | tee "$B/sources-network.json"; [ "${PIPESTATUS[0]}" = 0 ] || die "drop-in refusé"
  "${SRCS[@]}" --restart | tee -a "$B/sources-network.json"; [ "${PIPESTATUS[0]}" = 0 ] || die "redémarrage en échec : sudo bash $0 rollback ou --remove-network"
  systemctl show jarvis-hermes-pilot-system.service -p IPAddressAllow
  echo; echo "✅ Service privé : lecture HA/InfluxDB possible. Suite : fichiers Windows, puis sudo bash $0 windows-mcp"
}

windows_mcp_phase() {
  B=$(cat "$LAST" 2>/dev/null) || die "aucune installation enregistrée ($LAST)"
  [ "$(active)" = active ] && die "$UNIT est actif : l'arrêter d'abord (aucune mission en cours)"
  say "WINDOWS-MCP — contrôle (lecture seule)"
  "${BIND[@]}" --check || die "refusé : rien n'a été modifié"
  confirm EPINGLER "Copies du superviseur (2 fichiers MCP), sourceFiles et windows-bindings.json + bindingsSha256 mis aux nouvelles empreintes. Sauvegarde dans $B/bindings-update. Tant que Windows n'a pas les mêmes fichiers, le superviseur refusera toute session (sans dommage)."
  "${BIND[@]}" --apply --backup "$B" | tee "$B/windows-mcp.json"; [ "${PIPESTATUS[0]}" = 0 ] || die "échec (état précédent restauré)"
  echo; echo "✅ Côté superviseur à jour. Suite : sudo bash $0 ui-update, puis activate"
}

RECON=(python3 -I "$SRC/ops/demand-simple/reconcile.py")
reconcile_phase() {
  say "RECONCILE — missions incertaines (lecture seule)"
  "${RECON[@]}" --check || die "lecture impossible"
  MID=${2:-}
  [ -n "$MID" ] || { echo; echo "Pour fermer une mission : sudo bash $0 reconcile <mission_id> (après avoir vérifié qu'aucun Hermes ne tourne sur Windows)"; return 0; }
  confirm "FERMER-${MID:0:8}" "La mission $MID passe en ÉCHEC (jamais rejouée), la file est libérée, un événement est AJOUTÉ (rien n'est effacé). Superviseur (si aucun lease) et service privé arrêtés pendant l'écriture, service privé redémarré ensuite. À faire seulement si aucune session Hermes ne tourne sur Windows."
  "${RECON[@]}" --close "$MID" --windows-idle-confirmed --confirm "FERMER-${MID:0:8}" || die "fermeture refusée : voir ci-dessus"
  echo "✅ Mission fermée. Relancer le superviseur : sudo bash $0 activate"
}

windows_mcp_revert_phase() {
  B=$(cat "$LAST" 2>/dev/null) || die "aucune sauvegarde enregistrée"
  confirm RESTAURER-MCP "Copies du superviseur, sourceFiles et bindings remis à l'état d'avant windows-mcp."
  "${BIND[@]}" --revert --backup "$B" || die "restauration incomplète"
}

activate() {
  B=$(cat "$LAST" 2>/dev/null) || die "aucune installation enregistrée"
  [ -f "$B/dry-start.ok" ] || die "démarrage à vide non validé : lancer dry-start d'abord"
  [ "$(active)" = active ] && die "$UNIT déjà actif"
  confirm ACTIVER "enabled=true puis démarrage. Le superviseur prendra la PROCHAINE demande en file : il peut réveiller Windows et le GPU. Jamais d'enable au boot."
  say "enabled → true"; set_enabled true
  S=$(date '+%Y-%m-%d %H:%M:%S'); systemctl reset-failed "$UNIT" 2>/dev/null; systemctl start "$UNIT"; sleep 6
  say "état"; systemctl show "$UNIT" -p ActiveState -p SubState -p Result -p UnitFileState
  say "journal"; journal_since "$UNIT" "$S" | tail -10 | tee "$B/activate.txt"
}

rollback() {
  B=$(cat "$LAST" 2>/dev/null) || die "aucune sauvegarde enregistrée"
  [ -d "$B/etc" ] || die "sauvegarde incomplète : $B"
  confirm RESTAURER "Arrêt du superviseur, retour de l'interface et des fichiers du service privé et désarmement s'ils ont été faits, puis restauration exacte depuis $B (/etc, unités, /opt, table nft)."
  YES=1 route_revert_phase || die "restauration de l'aiguillage impossible : arrêt"
  while [ -n "$("${FUP[@]}" --pending --backup "$B")" ]; do YES=1 ui_revert_phase || die "restauration de l'interface impossible : arrêt"; done
  while [ -n "$("${BIND[@]}" --pending --backup "$B")" ]; do YES=1 windows_mcp_revert_phase || die "restauration MCP impossible : arrêt"; done
  "${SRCS[@]}" --remove-network >/dev/null || die "retrait du drop-in réseau impossible : arrêt"
  echo "   (la suppression de DoseLab, si faite, est irréversible par décision ; sources.json est conservé)"
  while [ -n "$("${UPD[@]}" --pending --backup "$B")" ]; do YES=1 private_revert_phase || die "restauration du service privé impossible : arrêt"; done
  if [ -f "$B/pilot-config.json" ]; then YES=1 disarm_phase || die "désarmement impossible : restauration interrompue"; fi
  systemctl stop "$UNIT" 2>/dev/null
  rm -rf "$C" && cp -a "$B/etc" "$C"
  for u in "$UNIT" "$BOOT_UNIT" "$OLD_UNIT"; do
    if [ -e "$B/$u" ]; then cp -a "$B/$u" "/etc/systemd/system/$u"; else rm -f "/etc/systemd/system/$u"; fi
  done
  rm -rf "$OPT" "$OPT.previous"; [ -f "$B/opt.tar" ] && tar -C /opt -xpf "$B/opt.tar"
  nft delete table inet jarvis_hermes_supervisor 2>/dev/null
  [ -f "$C/egress.nft" ] && ! grep -qx absent "$B/nft-table.txt" && nft -f "$C/egress.nft"
  systemctl daemon-reload; systemctl reset-failed "$UNIT" "$BOOT_UNIT" "$OLD_UNIT" 2>/dev/null
  echo "✅ Restauré depuis $B (état d'avant installation)."
}

case "$PHASE" in
  pre) pre ;;
  check) check ;;
  install) install_phase ;;
  dry-start) dry_start ;;
  arm) arm_phase ;;
  disarm) disarm_phase ;;
  private-update) private_update_phase ;;
  real-reset) real_reset_phase ;;
  sources-config) sources_config_phase ;;
  sources-network) sources_network_phase ;;
  windows-mcp) windows_mcp_phase ;;
  windows-mcp-revert) windows_mcp_revert_phase ;;
  reconcile) reconcile_phase "$@" ;;
  private-revert) private_revert_phase ;;
  ui-update) ui_update_phase ;;
  ui-revert) ui_revert_phase ;;
  route-backend) route_backend_phase ;;
  route-revert) route_revert_phase ;;
  activate) activate ;;
  rollback) rollback ;;
  *) sed -n '2,28p' "$0"; exit 2 ;;
esac
