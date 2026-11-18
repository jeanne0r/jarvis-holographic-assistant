#!/usr/bin/env bash
set -euo pipefail
umask 077

export CLOUDSDK_CONFIG=/home/user/workspace/_secrets/google-cloud
export CLOUDSDK_CORE_DISABLE_USAGE_REPORTING=true
export CLOUDSDK_CORE_DISABLE_PROMPTS=false
mkdir -p "$CLOUDSDK_CONFIG"
chmod 700 "$CLOUDSDK_CONFIG"

printf '%s\n' 'Connexion Google pour lire la facturation du projet gemini-api-key-468113.'
printf '%s\n' 'Ouvre le lien affiché, choisis ton compte Google, puis colle le code uniquement dans ce terminal.'
printf '%s\n' 'Le client officiel Google exige la portée Google Cloud générale pour cette connexion.'
printf '%s\n' 'Le contrôle Jarvis préparé ci-dessous effectue uniquement des lectures de facturation et de métadonnées BigQuery.'

/home/user/workspace/_tools/google-cloud-sdk/bin/gcloud auth application-default login \
  --project=gemini-api-key-468113 \
  --no-launch-browser \
  --disable-quota-project \
  --scopes=openid,https://www.googleapis.com/auth/userinfo.email,https://www.googleapis.com/auth/cloud-platform

chmod 600 "$CLOUDSDK_CONFIG/application_default_credentials.json"
python3 /home/user/workspace/jarvis/google_billing_probe.py
