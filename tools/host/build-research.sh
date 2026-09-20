#!/bin/bash
# SPDX-License-Identifier: Apache-2.0
# Entry point for the existing 8c16g research host; extra arguments are targets.
set -e

if [ "$(id -u)" != 0 ]; then
    echo 'Run as root on the research host.' >&2
    exit 1
fi

project_root="$(cd -- "$(dirname -- "$(readlink -f -- "$0")")/../.." && pwd)"
source_tree="${GOLD_SOURCE_TREE:-$(dirname -- "$project_root")/source}"

# These names preserve artifact identity; the actual process UID is root.
export USER=builder LOGNAME=builder BUILD_USERNAME=builder
export HOME=/root
export USE_CCACHE=1 CCACHE_EXEC=/usr/bin/ccache
export CCACHE_DIR=/root/ccache
export GOGC="${GOGC:-50}" GOMEMLIMIT="${GOMEMLIMIT:-10GiB}"
export GOMAXPROCS="${GOMAXPROCS:-4}"

if [ "${1:-}" = --check-environment ]; then
    python3 - "$source_tree" <<'PY'
import json
import os
from pathlib import Path
import pwd
import sys
import tempfile

cache = Path(os.environ['CCACHE_DIR'])
if not cache.is_dir() or cache.is_symlink():
    raise SystemExit('Expected a real cache directory: ' + str(cache))
with tempfile.TemporaryFile(dir=cache) as probe:
    probe.write(b'gold-cache-check')
    probe.seek(0)
    if probe.read() != b'gold-cache-check':
        raise SystemExit('Cache read/write verification failed')
print(json.dumps({'uid': os.getuid(), 'euid': os.geteuid(),
                  'account': pwd.getpwuid(os.geteuid()).pw_name,
                  'home': os.environ['HOME'], 'ccache_dir': str(cache),
                  'cache_read_write_verified': True,
                  'build_username': os.environ['BUILD_USERNAME'],
                  'source_tree': sys.argv[1]}, indent=2))
PY
    exit 0
fi

extra_targets=()
for target in "$@"; do
    extra_targets+=(--extra-target "$target")
done
exec python3 "$project_root/tools/build-source.py" \
    --tree "$source_tree" --lunch lineage_gold-bp4a-userdebug \
    --out out-gold-standard --jobs "${JOBS:-2}" \
    --build-datetime "${BUILD_DATETIME:-$(date +%s)}" \
    "${extra_targets[@]}" --execute
