#!/bin/sh
set -eu

run_script=$(readlink -f "$0" 2>/dev/null || printf '%s\n' "$0")
run_root=$(CDPATH='' cd -- "$(dirname -- "$run_script")" && pwd -P)

if [ "$#" -eq 0 ]; then
    set -- --settings
fi

exec "$run_root/voice-input" "$@"
