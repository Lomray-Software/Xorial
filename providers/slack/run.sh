#!/usr/bin/env bash
# Slack provider launcher. Run from the Xorial repo root or anywhere.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [ ! -d "$HERE/.venv" ]; then
  echo "Creating venv in $HERE/.venv"
  python3 -m venv "$HERE/.venv"
fi

# shellcheck disable=SC1091
source "$HERE/.venv/bin/activate"
pip install -q -r "$HERE/requirements.txt"

exec python -m providers.slack.main
