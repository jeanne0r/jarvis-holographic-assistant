"""Read the standard Cloud Billing export; never infer an AI Studio wallet."""
import datetime as dt
from decimal import Decimal
import json
import os
from pathlib import Path
import subprocess
import tempfile
from urllib.parse import quote, urlencode
from zoneinfo import ZoneInfo

from google_billing_probe import CONFIG, SDK, PROJECT, GoogleError, get

ROOT = Path(__file__).parent
DATASET = 'jarvis_billing'
ACCOUNT = '010432-CB3297-D7195C'
ZONE = ZoneInfo('Europe/Zurich')
EXPORT_URL = 'https://console.cloud.google.com/billing/' + ACCOUNT + '/export?project=' + PROJECT
MAX_ROWS = 100000
# Verified against the authenticated Google Cloud Billing service catalog.
GEMINI_API_SERVICE = 'AEFD-7695-64FA'


def decode(field, value):
    if value is None:
        return None
    if field.get('mode') == 'REPEATED':
        return [decode({**field, 'mode': 'NULLABLE'}, item['v']) for item in value]
    if field.get('type') in ('RECORD', 'STRUCT'):
        return decode_row(field.get('fields', []), value)
    return value


def decode_row(fields, row):
    values = row.get('f', [])
    if len(values) != len(fields):
        raise ValueError('Schéma Google modifié pendant la lecture.')
    return {field['name']: decode(field, item.get('v')) for field, item in zip(fields, values)}


def timestamp(value):
    try:
        return dt.datetime.fromtimestamp(float(value), dt.timezone.utc)
    except (ValueError, TypeError):
        return dt.datetime.fromisoformat(value.replace('Z', '+00:00'))


def aggregate(rows, now):
    totals = {}
    periods = {}
    latest_usage = latest_export = None
    matched = 0
    for row in rows:
        if (row.get('project') or {}).get('id') != PROJECT:
            continue
        cost = Decimal(str(row['cost']))
        currency = row['currency']
        if not cost.is_finite() or not isinstance(currency, str) or len(currency) != 3:
            raise ValueError('Montant Google invalide.')
        for credit in row.get('credits') or []:
            amount = Decimal(str(credit['amount']))
            if not amount.is_finite():
                raise ValueError('Crédit Google invalide.')
            cost += amount
        start = timestamp(row['usage_start_time'])
        day = start.astimezone(ZONE).date().isoformat()
        key = (day, currency)
        totals[key] = totals.get(key, Decimal(0)) + cost
        end = timestamp(row.get('usage_end_time') or row['usage_start_time'])
        service_id = (row.get('service') or {}).get('id', '')
        period_key = (start.isoformat(), end.isoformat(), currency, service_id)
        periods[period_key] = periods.get(period_key, Decimal(0)) + cost
        latest_usage = max(latest_usage, end) if latest_usage else end
        if row.get('export_time'):
            exported = timestamp(row['export_time'])
            latest_export = max(latest_export, exported) if latest_export else exported
        matched += 1
    today = now.astimezone(ZONE).date().isoformat()
    today_totals = [{'currency': currency, 'amount': float(amount)} for (day, currency), amount in sorted(totals.items()) if day == today]
    return {'day': today, 'today': today_totals, 'matchedRows': matched,
            'latestUsageDay': max((day for day, _currency in totals), default=None),
            'periods': [{'start': start, 'end': end, 'currency': currency, 'amount': float(amount),
                         'serviceId': service_id, 'walletEligible': service_id == GEMINI_API_SERVICE if service_id else None}
                        for (start, end, currency, service_id), amount in sorted(periods.items())],
            'daily': [{'day': day, 'currency': currency, 'amount': float(amount)} for (day, currency), amount in sorted(totals.items())],
            'latestUsageAt': latest_usage.isoformat() if latest_usage else None,
            'latestExportAt': latest_export.isoformat() if latest_export else None}


def sync():
    now = dt.datetime.now(dt.timezone.utc)
    result = {'state': 'pending_export', 'projectId': PROJECT, 'datasetId': DATASET,
              'checkedAt': now.isoformat(), 'day': now.astimezone(ZONE).date().isoformat(),
              'today': [], 'officialBalanceConnected': False, 'setupUrl': EXPORT_URL,
              'message': 'En attente de l’export Google. Le solde prépayé n’est pas fourni par cet export.'}
    if not (CONFIG / 'application_default_credentials.json').exists():
        return {**result, 'state': 'authentication_required', 'message': 'Connexion Google requise.'}
    auth = subprocess.run([SDK, 'auth', 'application-default', 'print-access-token'],
                          env=dict(os.environ, CLOUDSDK_CONFIG=str(CONFIG), CLOUDSDK_CORE_DISABLE_USAGE_REPORTING='true'),
                          capture_output=True, text=True, timeout=30)
    if auth.returncode or not auth.stdout.strip():
        return {**result, 'state': 'authentication_required', 'message': 'Connexion Google à renouveler.'}
    token = auth.stdout.strip()
    base = f'https://bigquery.googleapis.com/bigquery/v2/projects/{PROJECT}/datasets/{DATASET}/tables'
    try:
        listing = get(base + '?maxResults=1000', token)
        expected = 'gcp_billing_export_v1_' + ACCOUNT.replace('-', '_')
        table = next((item['tableReference']['tableId'] for item in listing.get('tables', [])
                      if item.get('tableReference', {}).get('tableId', '').lower() == expected.lower()), None)
        if not table:
            return result
        table_url = base + '/' + quote(table, safe='')
        metadata = get(table_url, token)
        fields = metadata['schema']['fields']
        if not {'project', 'cost', 'currency', 'usage_start_time'}.issubset({field['name'] for field in fields}):
            raise ValueError('Le schéma ne correspond pas à un export standard Cloud Billing.')
        if int(metadata.get('numRows', 0)) > MAX_ROWS:
            return {**result, 'state': 'capacity_required', 'message': 'Export volumineux : lecteur à adapter avant de publier des montants partiels.'}
        rows = []
        page = None
        while True:
            params = {'maxResults': 1000}
            if page:
                params['pageToken'] = page
            batch = get(table_url + '/data?' + urlencode(params), token)
            rows.extend(decode_row(fields, row) for row in batch.get('rows', []))
            if len(rows) > MAX_ROWS:
                raise ValueError('Export trop volumineux pour ce lecteur.')
            page = batch.get('pageToken')
            if not page:
                break
        after = get(table_url, token)
        if metadata.get('lastModifiedTime') != after.get('lastModifiedTime') or int(after.get('numRows', 0)) != len(rows):
            return {**result, 'state': 'export_updating', 'message': 'Export Google en cours de mise à jour ; nouvelle lecture au prochain cycle.'}
        summary = aggregate(rows, now)
        message = 'Coûts publiés par Google pour ce projet, crédits/remises inclus. Publication différée et révisable ; le solde du portefeuille reste distinct.'
        if not summary['today']:
            latest_day = summary['latestUsageDay']
            if latest_day:
                date = dt.date.fromisoformat(latest_day).strftime('%d.%m.%Y')
                message = f'Google connecté · dernière journée reçue : {date}. Les coûts du jour ne sont pas encore publiés dans cet export.'
            else:
                message = 'Google connecté · table reçue, mais aucune ligne pour ce projet à ce stade.'
        return {**result, **summary, 'state': 'ready' if summary['today'] else 'awaiting_today',
                'tableId': table, 'rowsRead': len(rows), 'source': 'google-cloud-billing-export',
                'message': message}
    except GoogleError as error:
        if error.status == 404:
            return result
        return {**result, 'state': 'access_error', 'httpStatus': error.status, 'reasons': error.reasons,
                'message': 'Lecture Google indisponible. Vérifie les autorisations et le service BigQuery.'}


def main():
    try:
        result = sync()
    except Exception:
        result = {'state': 'sync_error', 'checkedAt': dt.datetime.now(dt.timezone.utc).isoformat(),
                  'projectId': PROJECT, 'today': [], 'setupUrl': EXPORT_URL,
                  'message': 'Synchronisation Google indisponible. Aucun montant partiel publié.', 'officialBalanceConnected': False}
    paths = [ROOT / 'data' / 'google-costs.json']
    if result.get('source') == 'google-cloud-billing-export' and 'periods' in result:
        paths.insert(0, ROOT / 'data' / 'google-costs-last-good.json')
    for path in paths:
        fd, temporary = tempfile.mkstemp(dir=path.parent, prefix='.google-costs-')
        with os.fdopen(fd, 'w') as output:
            json.dump(result, output, ensure_ascii=False, indent=2)
        os.replace(temporary, path)
    print(json.dumps({'state': result['state'], 'checkedAt': result['checkedAt'], 'rowsRead': result.get('rowsRead', 0)}))


if __name__ == '__main__':
    main()
