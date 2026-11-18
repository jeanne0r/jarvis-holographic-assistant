"""Local estimates only. Never an authoritative Google billing balance."""
import datetime as dt
from decimal import Decimal
import json
import math
import os
from pathlib import Path
import sqlite3
import sys
import urllib.request
import xml.etree.ElementTree as ET
from zoneinfo import ZoneInfo

ZONE = ZoneInfo('Europe/Zurich')
KNOWN_MODELS = {'gemini-3.8-live', 'gemini-3.8-live-extended-thinking', 'gemini-3.1-flash-live-preview'}
# Nanodollars/token = USD/million tokens * 1000. Public standard paid prices.
RATES = {'inputText': 750, 'inputAudio': 3000, 'inputImage': 1000,
         'outputText': 4500, 'outputAudio': 12000}
PRICE_DATE = '2026-11-12'
SPEECH_MODELS = {'gemini-3.5-transcribe', 'gemini-3.8-flash-lite-tts', 'gemini-3.5-flash-lite'}

def model_rates(model, occurred):
    if model == 'gemini-3.5-flash-lite':
        return {'inputText':300, 'inputAudio':300, 'inputImage':300, 'outputText':2500, 'outputAudio':2500}
    if model == 'gemini-3.5-transcribe':
        return {'inputText':2000, 'inputAudio':2000, 'inputImage':2000, 'outputText':12000, 'outputAudio':12000}
    if model == 'gemini-3.8-flash-lite-tts':
        factor = 1 if occurred.date() < dt.date(2027,1,1) else 2
        return {'inputText':500*factor, 'inputAudio':500*factor, 'inputImage':500*factor, 'outputText':6000*factor, 'outputAudio':6000*factor}
    return RATES


def google_snapshot(name='google-costs.json'):
    try:
        return json.loads((Path(__file__).parent / 'data' / name).read_text())
    except (OSError, ValueError):
        return {'state': 'not_connected', 'today': [], 'message': 'Source de facturation Google non connectée.'}


def google_credit(balance, current, cached, now):
    snapshot = current if 'periods' in current else cached
    reference = dt.datetime.fromisoformat(balance.get('referenceAt', balance['updatedAt']))
    spent = Decimal(0)
    prorated = False
    mismatch = False
    scope_unknown = False
    eligible_after_reference = False
    for period in snapshot.get('periods', []):
        start = dt.datetime.fromisoformat(period['start'])
        end = dt.datetime.fromisoformat(period['end'])
        if end <= reference:
            continue
        if balance.get('walletScope') == 'gemini-api':
            if period.get('walletEligible') is False:
                continue
            if period.get('walletEligible') is not True:
                scope_unknown = True
                continue
        if period['currency'] != balance['currency']:
            mismatch = True
            continue
        eligible_after_reference = True
        amount = Decimal(str(period['amount']))
        if not amount.is_finite():
            raise ValueError('Montant Google invalide.')
        if start < reference:
            duration = (end - start).total_seconds()
            if duration <= 0:
                continue
            amount *= Decimal(str((end - reference).total_seconds())) / Decimal(str(duration))
            prorated = True
        spent += amount
    checked = snapshot.get('checkedAt')
    stale = not checked or now - dt.datetime.fromisoformat(checked) > dt.timedelta(minutes=45) or snapshot is not current
    state = 'scope_unknown' if scope_unknown else 'currency_mismatch' if mismatch else 'waiting_google' if 'periods' not in snapshot or not eligible_after_reference else 'stale' if stale else 'calculated'
    return {**balance, 'source': 'google-export-estimate', 'deducted': float(spent),
            'remaining': None if mismatch or scope_unknown else float(Decimal(str(balance['amount'])) - spent),
            'status': state, 'prorated': prorated, 'googleCheckedAt': checked,
            'latestUsageAt': snapshot.get('latestUsageAt')}


def integer(value, name):
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 100_000_000:
        raise ValueError('Compteur invalide : ' + name)
    return value


def estimate(usage, rates=None):
    rates = rates or RATES
    if not isinstance(usage, dict):
        raise ValueError('Usage invalide.')
    cost = 0
    tokens = {}
    for direction, total_name, details_name in [
        ('input', 'promptTokenCount', 'promptTokensDetails'),
        ('output', 'responseTokenCount', 'responseTokensDetails'),
    ]:
        total = integer(usage.get(total_name, 0), total_name)
        details = usage.get(details_name, [])
        if not isinstance(details, list) or len(details) > 20:
            raise ValueError('Détail des tokens invalide.')
        counted = 0
        for row in details:
            if not isinstance(row, dict):
                raise ValueError('Détail des tokens invalide.')
            count = integer(row.get('tokenCount', 0), 'tokenCount')
            modality = row.get('modality')
            if modality == 'TEXT':
                rate = rates[direction + 'Text']
            elif direction == 'input' and modality in ('IMAGE', 'VIDEO'):
                rate = rates['inputImage']
            else:
                rate = rates[direction + 'Audio']
            cost += count * rate
            counted += count
        if counted > total:
            raise ValueError('Total des tokens incohérent.')
        # If Google omits modality details, use the higher audio rate for the
        # unclassified remainder rather than silently underestimating it.
        cost += (total - counted) * rates[direction + 'Audio']
        tokens[direction] = total
        tokens[direction+'Modalities'] = [{'modality':r.get('modality'),'tokenCount':r.get('tokenCount',0)} for r in details]
        tokens[direction+'Unclassified'] = total-counted
    thoughts = integer(usage.get('thoughtsTokenCount', 0), 'thoughtsTokenCount')
    cost += thoughts * rates['outputText']
    tokens['thoughts'] = thoughts
    return cost, tokens


def fx_quote(currency):
    if currency == 'USD':
        return 1.0, dt.datetime.now(dt.timezone.utc).date().isoformat()
    # Reference conversion for estimates, not Google's card/account FX rate.
    try:
        with urllib.request.urlopen('https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml', timeout=8) as response:
            root = ET.fromstring(response.read(100000))
        rates = {'EUR': 1.0}
        date = None
        for node in root.iter():
            if 'time' in node.attrib:
                date = node.attrib['time']
            if 'currency' in node.attrib:
                rates[node.attrib['currency']] = float(node.attrib['rate'])
        return rates[currency] / rates['USD'], date
    except Exception:
        raise ValueError('Taux de change indisponible. Réessaie ou indique le solde en USD.') from None


class Ledger:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.db = sqlite3.connect(self.path, timeout=10)
        os.chmod(self.path, 0o600)
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.executescript('''
          CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
          CREATE TABLE IF NOT EXISTS sessions (id TEXT PRIMARY KEY, model TEXT NOT NULL, created TEXT NOT NULL);
          CREATE TABLE IF NOT EXISTS reports (
            session_id TEXT NOT NULL, sequence INTEGER NOT NULL, received TEXT NOT NULL,
            day TEXT NOT NULL, cost_nano INTEGER, tokens TEXT NOT NULL,
            PRIMARY KEY(session_id, sequence));
          CREATE INDEX IF NOT EXISTS reports_day ON reports(day);
        ''')
        self.db.execute('INSERT OR IGNORE INTO settings VALUES (?,?)', ('trackingSince', dt.datetime.now(dt.timezone.utc).isoformat()))
        self.db.commit()

    def setting(self, key):
        row = self.db.execute('SELECT value FROM settings WHERE key=?', (key,)).fetchone()
        return json.loads(row[0]) if row and key == 'balance' else row[0] if row else None

    def session(self, data, now):
        sid = data.get('id')
        model = data.get('model')
        if not isinstance(sid, str) or len(sid) != 36 or not isinstance(model, str) or len(model) > 150:
            raise ValueError('Session invalide.')
        self.db.execute('INSERT INTO sessions VALUES (?,?,?)', (sid, model.replace('models/', ''), now.isoformat()))
        self.db.commit()
        return {'registered': True}

    def report(self, data, now):
        seq = integer(data.get('sequence'), 'sequence')
        if not 1 <= seq <= 10000:
            raise ValueError('Rapport invalide.')
        row = self.db.execute('SELECT model,created FROM sessions WHERE id=?', (data.get('sessionId'),)).fetchone()
        if not row:
            raise ValueError('Session de suivi inconnue. Recharge Jarvis.')
        if now - dt.datetime.fromisoformat(row[1]) > dt.timedelta(days=7):
            raise ValueError('Session de suivi expirée.')
        occurred = now
        if data.get('occurredAt'):
            try:
                occurred = dt.datetime.fromisoformat(data['occurredAt'].replace('Z', '+00:00'))
                created = dt.datetime.fromisoformat(row[1])
                if occurred.tzinfo is None or occurred < created - dt.timedelta(minutes=5) or occurred > now + dt.timedelta(minutes=5):
                    raise ValueError()
            except (ValueError, TypeError, AttributeError):
                raise ValueError('Date du relevé invalide.') from None
        cost, tokens = estimate(data.get('usage'), model_rates(row[0], occurred))
        if data.get('incomplete') is True:
            cost = None
            tokens['incomplete'] = True
        # A retry of the same report must never debit the estimate twice.
        self.db.execute('INSERT OR IGNORE INTO reports VALUES (?,?,?,?,?,?)',
                        (data['sessionId'], seq, occurred.isoformat(), occurred.astimezone(ZONE).date().isoformat(),
                         cost if row[0] in KNOWN_MODELS | SPEECH_MODELS else None, json.dumps(tokens)))
        self.db.commit()
        return self.summary(now)

    def summary(self, now):
        google = google_snapshot()
        day = now.astimezone(ZONE).date().isoformat()
        total, unknown = self.db.execute('SELECT coalesce(sum(cost_nano),0),sum(cost_nano IS NULL) FROM reports').fetchone()
        today, today_unknown, reports = self.db.execute(
            'SELECT coalesce(sum(cost_nano),0),sum(cost_nano IS NULL),count(*) FROM reports WHERE day=?', (day,)).fetchone()
        balance = self.setting('balance')
        credit = None
        if balance and balance.get('deductionSource') == 'google-export':
            credit = google_credit(balance, google, google_snapshot('google-costs-last-good.json'), now)
        elif balance:
            if 'anchorRowid' in balance:
                after = (balance['anchorRowid'], balance['updatedAt'])
                spent, pending_unknown = self.db.execute('SELECT coalesce(sum(cost_nano),0),sum(cost_nano IS NULL) FROM reports WHERE rowid>? AND received>=?', after).fetchone()
            else:
                spent = total - balance['anchorNano']
                pending_unknown = self.db.execute('SELECT count(*) FROM reports WHERE cost_nano IS NULL AND received>=?', (balance['updatedAt'],)).fetchone()[0]
            spent /= 1e9
            credit = {**{k: v for k, v in balance.items() if k not in ('anchorNano', 'anchorRowid')},
                      'remaining': balance['amount'] - spent * balance['usdRate'] if not pending_unknown else None,
                      'source': 'manual-estimate'}
        return {'day': day, 'timezone': 'Europe/Zurich', 'currency': 'USD',
                'todayUsd': today / 1e9 if not today_unknown else None,
                'knownTodayUsd': today / 1e9, 'totalUsd': total / 1e9,
                'reportsToday': reports, 'unknownPriceReports': unknown or 0,
                'trackingSince': self.setting('trackingSince'), 'balance': credit,
                'updatedAt': now.isoformat(), 'priceDate': PRICE_DATE,
                'pricingUrl': 'https://ai.google.dev/gemini-api/docs/pricing',
                'billingUrl': 'https://aistudio.google.com/billing',
                'google': {k: v for k, v in google.items() if k not in ('periods', 'daily')}}

    def balance(self, data, now):
        amount, currency = data.get('amount'), data.get('currency')
        if isinstance(amount, bool) or not isinstance(amount, (int, float)) or not math.isfinite(amount) or not 0 <= amount <= 1_000_000:
            raise ValueError('Indique un solde entre 0 et 1 000 000.')
        if currency not in ('USD', 'CHF', 'EUR'):
            raise ValueError('Devise inconnue.')
        source = data.get('deductionSource', 'local-estimate')
        if source not in ('local-estimate', 'google-export'):
            raise ValueError('Source de consommation inconnue.')
        if source == 'google-export':
            reference = dt.datetime.fromisoformat(data.get('referenceAt', now.isoformat()))
            if reference.tzinfo is None or reference > now + dt.timedelta(minutes=5) or now - reference > dt.timedelta(days=7):
                raise ValueError('Date du solde invalide.')
            value = {'amount': amount, 'currency': currency, 'deductionSource': source,
                     'updatedAt': now.isoformat(), 'referenceAt': reference.isoformat(), 'overlapPolicy': 'prorata', 'walletScope': 'gemini-api'}
            self.db.execute('INSERT OR REPLACE INTO settings VALUES (?,?)', ('balance', json.dumps(value)))
            self.db.commit()
            return self.summary(now)
        rate, rate_date = fx_quote(currency)
        # Serialize the anchor with incoming usage. Never reset daily costs.
        self.db.execute('BEGIN IMMEDIATE')
        total = self.db.execute('SELECT coalesce(sum(cost_nano),0) FROM reports').fetchone()[0]
        last_report = self.db.execute('SELECT coalesce(max(rowid),0) FROM reports').fetchone()[0]
        value = {'amount': amount, 'currency': currency, 'usdRate': rate,
                 'fxDate': rate_date, 'updatedAt': now.isoformat(), 'anchorNano': total, 'anchorRowid': last_report}
        self.db.execute('INSERT OR REPLACE INTO settings VALUES (?,?)', ('balance', json.dumps(value)))
        self.db.commit()
        return self.summary(now)


def main():
    action = sys.argv[1]
    data = json.load(sys.stdin)
    path = os.environ.get('JARVIS_USAGE_DB', str(Path(__file__).parent / 'data' / 'voice-usage.sqlite'))
    ledger = Ledger(path)
    now = dt.datetime.now(dt.timezone.utc)
    if action == 'session':
        return ledger.session(data, now)
    if action == 'report':
        return ledger.report(data, now)
    if action == 'balance':
        return ledger.balance(data, now)
    if action == 'summary':
        return ledger.summary(now)
    raise ValueError('Action inconnue.')


if __name__ == '__main__':
    try:
        print(json.dumps({'ok': True, 'data': main()}))
    except Exception as error:
        print(json.dumps({'ok': False, 'error': str(error) if isinstance(error, ValueError) else 'Suivi des coûts momentanément indisponible.'}))
        sys.exit(1)
