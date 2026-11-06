#!/usr/bin/env bash
set -Eeuo pipefail
[[ ${1:-} == --backup && -n ${2:-} && ${3:-} == --target && ${4:-} == lab-web-restore-* ]] || { echo 'Usage: restore-verify.sh --backup /private/batch --target lab-web-restore-unique'; exit 2; }
exec python3 "$(dirname "$0")/backup_restore.py" restore "$2" "$4"
