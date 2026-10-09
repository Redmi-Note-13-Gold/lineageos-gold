#!/bin/bash
# Build LineageOS for gold on a host with little RAM (ours has 8 cores and 14 GB).
# Usage, from the top of the Android tree: build.sh [make targets...]   (default: bacon)
#
# Environment, all optional:
#   SOURCE_TREE   the Android tree, if not the current directory
#   JOBS          parallel jobs for m (default 4)
#   CCACHE_DIR    ccache directory (default $HOME/ccache)
#   GOGC, GOMEMLIMIT   limits for soong_build (default 50 and 10GiB)
#   LINEAGE_BUILD_DATE   see below
set -euo pipefail

here=$(dirname -- "$(readlink -f -- "$0")")

# A service manager may start this without HOME.
export HOME="${HOME:-/root}"
CCACHE_EXEC="${CCACHE_EXEC:-$(command -v ccache || true)}"
if [ -n "$CCACHE_EXEC" ]; then
    export USE_CCACHE=1 CCACHE_EXEC CCACHE_DIR="${CCACHE_DIR:-$HOME/ccache}"
fi
# soong_build alone needs more than this host's RAM unless the Go GC is told to stay under it.
export GOGC="${GOGC:-50}" GOMEMLIMIT="${GOMEMLIMIT:-10GiB}"

cd "${SOURCE_TREE:-$PWD}"
[ -f build/envsetup.sh ] || {
    echo "Run this from the top of the Android tree, or set SOURCE_TREE." >&2
    exit 1
}

apply_patch() {
    git -C "$1" apply --reverse --check "$here/$2" 2>/dev/null || git -C "$1" apply "$here/$2"
}
# soong_ui scrubs the environment; this lets the two Go variables above through.
apply_patch build/soong soong-memory-env.patch
# ro.lineage.version carries the build date, and Soong redoes its whole analysis
# when it changes. That takes hours here, so keep the date this out/ started with.
apply_patch vendor/lineage lineage-build-date.patch
mkdir -p out
export LINEAGE_BUILD_DATE="${LINEAGE_BUILD_DATE:-$(cat out/.lineage_build_date 2>/dev/null || date -u +%Y%m%d)}"
echo "$LINEAGE_BUILD_DATE" > out/.lineage_build_date

set +u
source build/envsetup.sh
breakfast gold userdebug
set -u
m -j"${JOBS:-4}" "${@:-bacon}"
