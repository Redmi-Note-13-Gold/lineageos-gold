#!/bin/bash
# Build LineageOS for gold on a host with little RAM (ours has 8 cores and 16 GB).
# Usage, from the top of the Android tree: build.sh [make targets...]   (default: bacon)
#
# Environment, all optional:
#   SOURCE_TREE   the Android tree, if not the current directory
#   JOBS          parallel jobs for m (default 4)
#   CCACHE_DIR    ccache directory (default $HOME/ccache)
#   GOGC, GOMEMLIMIT   limits for soong_build (default 50 and 10GiB)
#   SOONG_BUILD_GODEBUG   GODEBUG for soong_build alone, e.g. gctrace=1 to log its garbage collector
set -euo pipefail

here=$(dirname -- "$(readlink -f -- "$0")")

# A service manager may start this without HOME.
export HOME="${HOME:-/root}"
CCACHE_EXEC="${CCACHE_EXEC:-$(command -v ccache || true)}"
if [ -n "$CCACHE_EXEC" ]; then
    export USE_CCACHE=1 CCACHE_EXEC CCACHE_DIR="${CCACHE_DIR:-$HOME/ccache}"
fi
# soong_build alone needs more than this host's RAM. These keep it at 20 to 23 GB; the README
# says how the part that does not fit is swapped.
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

set +u
source build/envsetup.sh
breakfast gold userdebug
set -u
m -j"${JOBS:-4}" "${@:-bacon}"
