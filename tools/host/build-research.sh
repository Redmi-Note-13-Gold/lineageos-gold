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

# Record the whole service invocation, including preflight failures and signals.
# The recursive entry still performs exactly the same layout/tool/build checks.
if [ -n "${INVOCATION_ID:-}" ] && [ "${GOLD_RECORDED_INVOCATION:-}" != "$INVOCATION_ID" ]; then
    exec python3 -B "$project_root/tools/host/build-invocation.py" \
        --records "$(dirname -- "$project_root")/jobs/build-invocations" -- \
        "$project_root/tools/host/build-research.sh" "$@"
fi

# Hidden-API encoding and packaging use these allowed, non-hermetic host tools.
# Check before graph/configuration work; temporary job-local tools may be on PATH.
for host_tool in unzip zip; do
    command -v "$host_tool" >/dev/null 2>&1 || {
        echo "Required Android host tool is missing from PATH: $host_tool" >&2
        exit 1
    }
done

# Fail before touching output if the data disk or source overlay is missing/mismatched.
python3 -B "$project_root/tools/host/check-research-layout.py" --source-tree "$source_tree" >/dev/null

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
import subprocess
import sys
import tempfile

cache = Path(os.environ['CCACHE_DIR'])
tree = Path(sys.argv[1]).resolve()
out = tree / 'out-gold-standard'
if out.exists() and out.stat().st_uid != os.geteuid():
    raise SystemExit('Managed output must belong to the actual build UID for nsjail: ' + str(out))
subprocess.run([str(tree / '.repo/repo/repo'), 'manifest', '-r'],
               cwd=tree, stdout=subprocess.DEVNULL, check=True)
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
                  'pinned_manifest_export_verified': True,
                  'output_owner_verified': True,
                  'research_layout_verified': True,
                  'build_username': os.environ['BUILD_USERNAME'],
                  'source_tree': str(tree)}, indent=2))
PY
    exit 0
fi

# Regenerate the build graph in the existing output, including Soong's native
# relocation of absolute output symlinks. This is not a ROM/package acceptance.
if [ "${1:-}" = --check-build-graph ]; then
    if [ "$#" != 1 ]; then
        echo '--check-build-graph takes no extra targets.' >&2
        exit 1
    fi
    # Match build-source.py's advisory lock before touching the managed output.
    exec 9>"$source_tree/.repo/gold-source-build.lock"
    flock -n 9 || { echo 'Another Gold build holds this source-tree lock.' >&2; exit 1; }
    python3 - "$source_tree" <<'PY_MARKER'
import json
from pathlib import Path
import sys

tree = Path(sys.argv[1]).resolve()
marker = tree / 'out-gold-standard/.gold-source-build.json'
if json.loads(marker.read_text()).get('source_tree') != str(tree):
    raise SystemExit('Existing output is not owned by this source entry')
PY_MARKER
    cd -- "$source_tree"
    unset OUT_DIR_COMMON_BASE
    export OUT_DIR=out-gold-standard
    export BUILD_DATETIME="${BUILD_DATETIME:-$(cat "$OUT_DIR/build_date.txt")}"
    export SOURCE_DATE_EPOCH="$BUILD_DATETIME"
    source build/envsetup.sh
    lunch lineage_gold-bp4a-userdebug
    m -j"${JOBS:-2}" nothing
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
