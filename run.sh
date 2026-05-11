#!/usr/bin/env bash
# -----------------------------------------------------------------------------
# Entrypoint for the LLM MT demo.
#
# What it does, in order:
#   1. Ensures a local secrets file (``settings.py``) exists; if missing,
#      it is seeded from ``settings-template.py``.
#   2. Activates a project-local virtualenv at ``.venv`` if one exists.
#   3. Optionally enables Python-level logging to a timestamped file.
#   4. Applies Django migrations (Django's own auth/contenttypes tables;
#      no application models are defined in Phase 1).
#   5. Starts the Django development server.
#
# Usage:
#   ./run.sh                              # normal run
#   ./run.sh --log                        # also write a timestamped log
#                                         # file (log-YYYYMMDD-HHMMSS.log)
#                                         # next to this script
#   ./run.sh --fetcher trafilatura        # select URL-extractor backend
#   ./run.sh --fetcher newspaper          # (trafilatura is the default)
#
# Environment overrides:
#   HOST   – bind address (default 127.0.0.1)
#   PORT   – TCP port      (default 8000)
# -----------------------------------------------------------------------------

set -euo pipefail
cd "$(dirname "$0")"

# 0. Parse command-line flags.
log_enabled=0
fetcher=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --log)
      log_enabled=1
      shift
      ;;
    --fetcher)
      [[ $# -ge 2 ]] || { echo "--fetcher requires a value" >&2; exit 2; }
      fetcher="$2"
      shift 2
      ;;
    --fetcher=*)
      fetcher="${1#--fetcher=}"
      shift
      ;;
    -h|--help)
      sed -n '2,/^# ---/p' "$0" | sed 's/^# \{0,1\}//'
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      echo "Use --help for usage." >&2
      exit 2
      ;;
  esac
done

if [[ -n "$fetcher" ]]; then
  export MT_FETCHER="$fetcher"
fi

# 1. Secrets file
if [[ ! -f settings.py ]]; then
  cp settings-template.py settings.py
  echo "Created settings.py from template; fill in HF_INFERENCE_ENDPOINT_TOKEN before Phase 2."
fi

# 2. Optional virtualenv
if [[ -d .venv ]]; then
  # shellcheck disable=SC1091
  source .venv/bin/activate
fi

# 3. Optional file logging.  When --log is passed, a fresh timestamped
#    log file is created next to this script and Django's logging config
#    is wired to write to it (see mtdemo/settings.py).
if [[ "$log_enabled" == "1" ]]; then
  ts=$(date +%Y%m%d-%H%M%S)
  export MT_LOG_FILE="$(pwd)/log-${ts}.log"
  echo "Logging Python errors to ${MT_LOG_FILE}"
fi

# 4. Migrations (idempotent)
python manage.py migrate --noinput

# 5. Dev server
HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-8000}"
exec python manage.py runserver "${HOST}:${PORT}"
