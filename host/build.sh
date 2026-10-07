#!/bin/bash
# Build LineageOS for gold on the 8-core / 14 GB host.
# Usage: build.sh [make targets...]   (default: bacon)
set -euo pipefail

source_tree=/srv/build/gold/source
here=$(dirname -- "$(readlink -f -- "$0")")

export HOME=/root
export USE_CCACHE=1 CCACHE_EXEC=/usr/bin/ccache CCACHE_DIR=/root/ccache
# soong_build alone needs more than this host's RAM unless the Go GC is told to stay under it.
export GOGC="${GOGC:-50}" GOMEMLIMIT="${GOMEMLIMIT:-10GiB}"

cd "$source_tree"

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
