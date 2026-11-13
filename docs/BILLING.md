# Usage and billing

Gemini and Codex use separate accounts/meters. A smaller Google balance does not describe Codex quota, and a Codex quota percentage is not a cash wallet balance.

## Google estimates

`usage.py` records provider usage metadata and computes local estimates. The bundled rate table is dated and model-specific. Check current provider prices before relying on it, especially after changing a model. Unknown/partial usage and search-grounding fees may leave an estimate incomplete. No claim of perfectly live billing is made.

The reference credit balance is entered manually. Jarvis subtracts tracked costs after that reference point; it cannot see recharges or other applications' spending through this estimate. The repository contains no starting balance.

## Optional official Google Cloud Billing data

1. Install the Google Cloud CLI and sign in with an account allowed to read your project's billing/export data.
2. In Cloud Billing, enable the **standard usage cost export** to a BigQuery dataset you control.
3. Set `GOOGLE_CLOUD_PROJECT`, `GOOGLE_BILLING_ACCOUNT` (ID without the `billingAccounts/` prefix) and `GOOGLE_BILLING_DATASET` in `.env`.
4. Authenticate ADC as the service OS user. For example:

```bash
gcloud auth application-default login --project=YOUR_PROJECT_ID
gcloud auth application-default set-quota-project YOUR_PROJECT_ID
```

5. Run the optional probe/sync with the same environment:

```bash
node --env-file=.env --input-type=module -e "import {spawnSync} from 'node:child_process'; spawnSync('python3',['google_billing_probe.py'],{stdio:'inherit'}); spawnSync('python3',['google_billing_sync.py'],{stdio:'inherit'});"
```

6. Schedule the sync if desired. Read access and BigQuery job/query permissions must match your own cloud policy; do not grant broad administrator access just to display costs.

Initial export population and billing updates can be delayed by hours or longer. Published costs are not the same as the AI Studio prepaid-wallet balance. The implementation does not claim an undocumented wallet API. See Google's [Cloud Billing export documentation](https://cloud.google.com/billing/docs/how-to/export-data-bigquery).

## Codex account limits

`openai-usage.mjs` reads the signed-in Codex app-server's account limits when the installed CLI/account exposes them. It may return unavailable or stale data. Account windows/credit details depend on the provider and account; do not infer an OpenAI API balance from those fields.
