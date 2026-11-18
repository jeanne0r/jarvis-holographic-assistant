"""Read-only Google billing/export discovery. Never prints credentials."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

ROOT = Path('/home/user/workspace/jarvis')
CONFIG = Path('/home/user/workspace/_secrets/google-cloud')
PROJECT = 'gemini-api-key-468113'
SDK = '/home/user/workspace/_tools/google-cloud-sdk/bin/gcloud'


class GoogleError(Exception):
    def __init__(self, status, reasons):
        self.status = status
        self.reasons = reasons


def get(url, token):
    # Every Google operation in this diagnostic is GET, and restricted to the
    # supplied project's billing association and BigQuery export metadata.
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme != 'https' or parsed.hostname not in ('cloudbilling.googleapis.com', 'bigquery.googleapis.com'):
        raise ValueError('Destination Google invalide.')
    request = urllib.request.Request(url, headers={'Authorization': 'Bearer ' + token})
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            return json.load(response)
    except urllib.error.HTTPError as error:
        try:
            data = json.load(error).get('error', {})
            reasons = [detail['reason'] for detail in data.get('details', []) if isinstance(detail.get('reason'), str)]
        except Exception:
            reasons = []
        # Do not expose raw Google errors or request headers/credentials.
        raise GoogleError(error.code, reasons) from None


def probe():
    result = {'projectId': PROJECT, 'checkedAt': datetime.now(timezone.utc).isoformat(),
              'officialCostsConnected': False, 'officialBalanceConnected': False,
              'officialBalanceStatus': 'No documented public AI Studio prepaid-wallet API found',
              'exportTables': []}
    if not (CONFIG / 'application_default_credentials.json').exists():
        return {**result, 'status': 'authentication_required',
                'message': 'Lance bash /home/user/workspace/jarvis/connect-google-billing.sh pour connecter Google.'}
    env = dict(os.environ, CLOUDSDK_CONFIG=str(CONFIG), CLOUDSDK_CORE_DISABLE_USAGE_REPORTING='true')
    credentials = subprocess.run([SDK, 'auth', 'application-default', 'print-access-token'], env=env,
                                 capture_output=True, text=True, timeout=30)
    if credentials.returncode or not credentials.stdout.strip():
        return {**result, 'status': 'authentication_required', 'message': 'La connexion Google doit être renouvelée.'}
    token = credentials.stdout.strip()
    try:
        billing = get(f'https://cloudbilling.googleapis.com/v1/projects/{PROJECT}/billingInfo', token)
        result['billingEnabled'] = billing.get('billingEnabled', False)
        result['billingAccountName'] = billing.get('billingAccountName')
        if not result['billingEnabled']:
            return {**result, 'status': 'billing_not_enabled', 'message': 'Le projet ne déclare pas de facturation active. Aucun paramètre modifié.'}
    except GoogleError as error:
        return {**result, 'status': 'billing_access_required', 'httpStatus': error.status, 'reasons': error.reasons,
                'message': 'Google refuse la lecture du rattachement de facturation du projet. Vérifie compte, projet et autorisations.'}

    base = f'https://bigquery.googleapis.com/bigquery/v2/projects/{PROJECT}/datasets'
    try:
        datasets = get(base + '?maxResults=1000', token)
        for dataset in datasets.get('datasets', []):
            dataset_id = dataset['datasetReference']['datasetId']
            path = base + '/' + urllib.parse.quote(dataset_id, safe='') + '/tables?maxResults=1000'
            listing = get(path, token)
            for table in listing.get('tables', []):
                ref = table.get('tableReference', {})
                if ref.get('tableId', '').startswith(('gcp_billing_export_v1_', 'gcp_billing_export_resource_v1_', 'gcp_billing_export_focus_')):
                    result['exportTables'].append(ref)
        result['status'] = 'export_found' if result['exportTables'] else 'export_required'
        result['message'] = ('Export détecté ; schéma et périmètre à vérifier avant synchronisation des coûts.' if result['exportTables'] else
                             'Aucun export Cloud Billing trouvé dans ce projet. Il peut être absent ou situé dans un autre projet.')
    except GoogleError as error:
        result.update(status='bigquery_access_required', httpStatus=error.status, reasons=error.reasons,
                      message='Accès BigQuery indisponible. Vérifie que le service est activé et que le compte peut lire les exports.')
    return result


def main():
    try:
        result = probe()
    except Exception:
        result = {'projectId': PROJECT, 'status': 'check_failed', 'officialCostsConnected': False,
                  'officialBalanceConnected': False, 'message': 'Vérification Google indisponible. Réessaie dans un instant.'}
    path = ROOT / 'data' / 'google-billing-status.json'
    fd, temporary = tempfile.mkstemp(dir=path.parent, prefix='.google-billing-')
    with os.fdopen(fd, 'w') as output:
        json.dump(result, output, ensure_ascii=False, indent=2)
    os.replace(temporary, path)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
