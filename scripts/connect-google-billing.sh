#!/usr/bin/env bash
set -euo pipefail
: "${GOOGLE_CLOUD_PROJECT:?Export GOOGLE_CLOUD_PROJECT first}"
gcloud auth application-default login --project="$GOOGLE_CLOUD_PROJECT"
gcloud auth application-default set-quota-project "$GOOGLE_CLOUD_PROJECT"
python3 google_billing_probe.py
