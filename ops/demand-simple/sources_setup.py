#!/usr/bin/python3 -I
"""Real sources for the private Hermes service: read-only credentials and the network opening.

  --config               ask the HA / InfluxDB settings; tokens are typed hidden (getpass) and written
                         ONLY to /var/lib/jarvis-hermes-pilot/sources.json (owner of the state dir, 0600)
  --test                 read-only: one HA states read and one Influx entity list, counts only
  --network              systemd drop-in: IPAddressAllow= the IPs of the configured URLs (literal IPs,
                         no DNS); the unit file itself is untouched (the coordinator compares it)
  --remove-network       delete that drop-in
  --restart              restart the private service through the approved private-boot hook
Tokens are never printed, logged or passed on a command line. Home Assistant has no
read-only token and InfluxDB 3 Core only admin tokens: the read-only guarantee is
memory_manager/sources/readers.py (HA: GET /api/states, /api/history/period; Influx: GET
/api/v3/query_influxql); create a dedicated non-admin HA user and a dedicated Influx token anyway.
"""
import argparse, getpass, importlib.util, ipaddress, json, os, subprocess, sys, urllib.parse
from pathlib import Path

HERE = Path(__file__).resolve().parent
STATE = Path('/var/lib/jarvis-hermes-pilot')
UNIT = 'jarvis-hermes-pilot-system.service'
DROPIN = Path('/etc/systemd/system') / (UNIT + '.d') / 'real-sources.conf'


def literal_ip(url):
    host = urllib.parse.urlsplit(url).hostname or ''
    try: ip = ipaddress.ip_address(host)
    except ValueError: raise ValueError('Use a literal IP in the URL (no DNS in the confined service): ' + url) from None
    if ip.version != 4 or not ip.is_private or ip.is_loopback: raise ValueError('Private LAN IPv4 required: ' + url)
    return str(ip)


def validate(cfg):
    from_repo()
    from memory_manager.sources.readers import load
    load(cfg)          # URL shape, org/bucket allowlist; raises on anything malformed
    return sorted({literal_ip(c['url']) for k, c in cfg.items() if k in ('homeAssistant', 'influx') and c})


def from_repo():
    root = str(HERE.parents[1])
    if root not in sys.path: sys.path.insert(0, root)


def write_private(path, data, owner_of):
    st = Path(owner_of).stat()
    tmp = path.with_name('.' + path.name + '.new-' + os.urandom(3).hex())
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'w') as f: json.dump(data, f, indent=1); f.write('\n'); f.flush(); os.fsync(f.fileno())
    os.chown(tmp, st.st_uid, st.st_gid); os.replace(tmp, path)


def ask_config(ask=input, secret=getpass.getpass):
    def q(label, default=''):
        v = ask('%s%s : ' % (label, ' [%s]' % default if default else '')).strip()
        return v or default
    cfg = {}
    if q('Configurer Home Assistant ? (o/n)', 'o').lower().startswith('o'):
        cfg['homeAssistant'] = {'url': q('URL Home Assistant', 'http://192.0.2.215:8123'),
                                'token': secret('Token HA (utilisateur dédié non-admin, saisie masquée) : ').strip()}
    if q('Configurer InfluxDB 3 ? (o/n)', 'o').lower().startswith('o'):
        cfg['influx'] = {'url': q('URL InfluxDB 3', 'http://192.0.2.187:8181'),
                         'databases': [b.strip() for b in q('Base(s) où écrit HA, séparées par des virgules', 'homeassistant').split(',') if b.strip()],
                         'token': secret('Token InfluxDB 3 (Core : admin seulement ; saisie masquée) : ').strip()}
    for c in cfg.values():
        if not c['token']: raise ValueError('Empty token')
    return cfg


def load_config(state=STATE):
    p = state / 'sources.json'; st = p.lstat()
    if p.is_symlink() or st.st_mode & 0o077 or st.st_uid != state.stat().st_uid: raise PermissionError('sources.json must be 0600, owned like ' + str(state))
    return json.loads(p.read_text())


def test(state=STATE):
    from_repo()
    from memory_manager.sources.readers import load
    readers = load(load_config(state)); out = {}
    if 'ha' in readers:
        r = readers['ha'].states(limit=1); out['home_assistant'] = {'entities': r['matched']}
    if 'influx' in readers:
        r = readers['influx'].entities(limit=1); out['influx'] = {'database': r['database'], 'entities': r['matched']}
    return {'passed': bool(out), **out, 'note': 'run as root from the host; the service itself is checked by /v1/health real_sources and the first mission'}


def network(ips, dropin=DROPIN, reload=True):
    text = '# Real sources (sources_setup.py): read-only HA / InfluxDB. Unit file untouched.\n[Service]\nIPAddressAllow=%s\n' % ' '.join(ip + '/32' for ip in ips)
    dropin.parent.mkdir(mode=0o755, exist_ok=True)
    tmp = dropin.with_name('.' + dropin.name + '.new'); tmp.write_text(text); os.chmod(tmp, 0o644); os.replace(tmp, dropin)
    if reload: subprocess.run(['systemctl', 'daemon-reload'], check=True, timeout=60)
    return {'passed': True, 'dropin': str(dropin), 'allow': ips}


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    g = p.add_mutually_exclusive_group(required=True)
    for a in ('config', 'test', 'network', 'remove-network', 'restart'): g.add_argument('--' + a, action='store_true')
    a = p.parse_args()
    if os.geteuid() != 0: sys.exit('root required')
    try:
        if a.config:
            cfg = ask_config(); ips = validate(cfg)
            write_private(STATE / 'sources.json', cfg, STATE)
            out = {'passed': True, 'written': str(STATE / 'sources.json'), 'sources': sorted(cfg), 'ips_for_network': ips}
        elif a.test: out = test()
        elif a.network: out = network(validate(load_config()))
        elif a.remove_network:
            if DROPIN.exists(): DROPIN.unlink()
            subprocess.run(['systemctl', 'daemon-reload'], check=True, timeout=60); out = {'passed': True, 'removed': str(DROPIN)}
        else:
            spec = importlib.util.spec_from_file_location('simple_arm', HERE / 'arm.py')
            arm = importlib.util.module_from_spec(spec); spec.loader.exec_module(arm)
            r = arm.Arm(); r._stop_supervisor_if_idle(); r.ctl('stop', arm.PILOT); ok = r._restart_private()
            out = {'passed': bool(ok), 'private_service_state': r.state(arm.PILOT), 'supervisor_state': r.state(arm.SUPERVISOR)}
    except Exception as e:
        # str(e) never contains a token: readers raise type names only; config errors name fields.
        print(json.dumps({'passed': False, 'error_type': type(e).__name__, 'error': str(e)[:400]})); sys.exit(2)
    print(json.dumps(out, indent=1, ensure_ascii=False)); sys.exit(0 if out.get('passed') else 2)


if __name__ == '__main__':
    main()
