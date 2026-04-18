#!/usr/bin/env bash
# Slack provider launcher. Safe to invoke from any CWD.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
XORIAL_ROOT="$(cd "$HERE/../.." && pwd)"

# claude-agent-sdk needs Python 3.10+. macOS system python3 is 3.9, and a
# non-interactive ssh shell often does not have /opt/homebrew/bin on PATH,
# so `python3` would resolve to the system one and pip would refuse the
# SDK. Walk a short list of known locations and pick the first 3.10+.
find_python() {
  local cand
  for cand in \
    /opt/homebrew/bin/python3.14 \
    /opt/homebrew/bin/python3.13 \
    /opt/homebrew/bin/python3.12 \
    /opt/homebrew/bin/python3.11 \
    /opt/homebrew/bin/python3 \
    /usr/local/bin/python3.14 \
    /usr/local/bin/python3.13 \
    /usr/local/bin/python3.12 \
    /usr/local/bin/python3.11 \
    /usr/local/bin/python3 \
    python3.14 python3.13 python3.12 python3.11 python3
  do
    if command -v "$cand" >/dev/null 2>&1; then
      if "$cand" -c 'import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)' 2>/dev/null; then
        echo "$cand"
        return 0
      fi
    fi
  done
  return 1
}

if [ ! -d "$HERE/.venv" ]; then
  PY=$(find_python) || {
    echo "ERROR: need Python 3.10+ (for claude-agent-sdk). Install one:" >&2
    echo "  brew install python@3.12   # or 3.11 / 3.13" >&2
    exit 1
  }
  echo "Creating venv in $HERE/.venv (using $PY)"
  "$PY" -m venv "$HERE/.venv"
fi

# shellcheck disable=SC1091
source "$HERE/.venv/bin/activate"
pip install -q -r "$HERE/requirements.txt"

# cd to Xorial repo root so `python -m providers.slack.main` resolves the package.
cd "$XORIAL_ROOT"
exec python -m providers.slack.main
