#!/usr/bin/env bash
# Compatibility entry point; all platforms share the same updater implementation.
set -eu
script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
for python in python3 python; do
  if command -v "$python" >/dev/null 2>&1 && "$python" -c 'import sys; sys.exit(sys.version_info < (3, 10))'; then
    exec "$python" "$script_dir/update-clankers.py" "$@"
  fi
done
printf '%s\n' 'Update Clankers requires Python 3.10+. No agents were updated.' >&2
exit 1
