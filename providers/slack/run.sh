#!/usr/bin/env bash
# Slack provider launcher. Safe to invoke from any CWD.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
XORIAL_ROOT="$(cd "$HERE/../.." && pwd)"

if [ ! -d "$HERE/.venv" ]; then
  echo "Creating venv in $HERE/.venv"
  python3 -m venv "$HERE/.venv"
fi

# shellcheck disable=SC1091
source "$HERE/.venv/bin/activate"
pip install -q -r "$HERE/requirements.txt"

# cd to Xorial repo root so `python -m providers.slack.main` resolves the package.
cd "$XORIAL_ROOT"
exec python -m providers.slack.main
