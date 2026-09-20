#!/bin/bash
# SPDX-License-Identifier: Apache-2.0
# Entry point for the existing 8c16g research host; extra arguments are targets.
set -e

if [ "$(id -u)" = 0 ]; then
    exec runuser -u goldbuild -- "$0" "$@"
fi
if [ "$(id -un)" != goldbuild ]; then
    echo 'Run as goldbuild, or as root to switch to that build account.' >&2
    exit 1
fi

project_root="$(cd -- "$(dirname -- "$(readlink -f -- "$0")")/../.." && pwd)"
source_tree="${GOLD_SOURCE_TREE:-$(dirname -- "$project_root")/source}"

# Keep the existing output identity and cache, while bounding Go's heap on 16G.
export USER=builder LOGNAME=builder BUILD_USERNAME=builder
export USE_CCACHE=1 CCACHE_EXEC=/usr/bin/ccache
export CCACHE_DIR=/srv/build/ccache-gold-betterr
export GOGC="${GOGC:-50}" GOMEMLIMIT="${GOMEMLIMIT:-10GiB}"
export GOMAXPROCS="${GOMAXPROCS:-4}"

extra_targets=()
for target in "$@"; do
    extra_targets+=(--extra-target "$target")
done
exec python3 "$project_root/tools/build-source.py" \
    --tree "$source_tree" --lunch lineage_gold-bp4a-userdebug \
    --out out-gold-standard --jobs "${JOBS:-2}" \
    --build-datetime "${BUILD_DATETIME:-$(date +%s)}" \
    "${extra_targets[@]}" --execute
