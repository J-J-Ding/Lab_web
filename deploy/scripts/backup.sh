#!/usr/bin/env bash
set -Eeuo pipefail
umask 077
[[ ${1:-} == --output && -n ${2:-} ]] || { echo 'Usage: backup.sh --output /absolute/private/batch-directory'; exit 2; }
exec python3 "$(dirname "$0")/backup_restore.py" backup "$2"
