#!/usr/bin/env bash
# Reviewed preparation only. Never run on the Codex/gateway host.
set -euo pipefail
if [[ "${PHASE3_INSTALL_APPROVED:-}" != YES || "$(hostname -s)" != jarvis-lab ]]; then
  echo 'Requires explicit approval and the dedicated jarvis-lab host.' >&2
  exit 1
fi
phase3_worktree="$(cd "$(dirname "$0")/.." && pwd)"
case "$phase3_worktree" in
  /home/user/workspace/*) ;;
  *) echo 'An isolated workspace checkout is required.' >&2; exit 1 ;;
esac
phase3_source="$phase3_worktree/data/hermes-upstream"
phase3_storage="$phase3_worktree/data/phase3/install"
# Fail before creating an incomplete install if Ubuntu is still preparing venv.
python3 -m ensurepip --version >/dev/null
[[ "$(git -C "$phase3_source" rev-parse HEAD)" == 4959268e312a21a361f248e49030d5f5df3984d5 ]]
[[ -z "$(git -C "$phase3_source" status --porcelain --untracked-files=no)" ]]
python3 - "$phase3_worktree" <<'PY'
import shutil, sys
if shutil.disk_usage(sys.argv[1]).free < 8 * 1024 ** 3:
    raise SystemExit('At least 8 GiB free required; no automatic cleanup or disk resize')
PY
# Refuse to overwrite an earlier environment. Bootstrap requires python3-venv.
[[ ! -e "$phase3_storage" ]]
mkdir -m 700 "$phase3_storage"
python3 -m venv "$phase3_storage/bootstrap"
"$phase3_storage/bootstrap/bin/python" -m pip install --disable-pip-version-check 'uv==0.13.8'
export UV_CACHE_DIR="$phase3_storage/cache"
export UV_PYTHON_INSTALL_DIR="$phase3_storage/python"
export UV_PROJECT_ENVIRONMENT="$phase3_storage/venv"
# sms extra only supplies the exact aiohttp pin needed by api_server; no SMS tool enabled.
"$phase3_storage/bootstrap/bin/uv" sync --project "$phase3_source" --locked --no-dev \
  --extra mcp --extra sms --python 3.14
"$phase3_storage/venv/bin/python" --version
# No setup wizard, daemon, cron, npm, browser, model pull, or agent startup.
