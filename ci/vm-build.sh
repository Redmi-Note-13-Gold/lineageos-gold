#!/bin/bash
# Startup script of the build VM that .github/workflows/build.yml creates. It builds one LineageOS
# package from source following local_manifests' README, puts the files in the bucket under
# runs/<run id>/ and then idles: the workflow deletes the VM as soon as it sees the status, and
# the VM's maximum run time deletes it if the workflow is gone.
#
# Instance metadata it reads: run-id, bucket, device-ref, vendor-ref, kernel-ref, gki,
# vendor-modules, snapshot-url (optional: a manifest snapshot of an earlier build to rebuild it).

set -uo pipefail
export HOME=/root  # startup scripts run without it; git and Soong need it
md() { curl -sf -H 'Metadata-Flavor: Google' "http://metadata.google.internal/computeMetadata/v1/instance/attributes/$1"; }
RUN=$(md run-id); BUCKET=$(md bucket)
DEVICE_REF=$(md device-ref); VENDOR_REF=$(md vendor-ref); KERNEL_REF=$(md kernel-ref)
GKI=$(md gki); VMODS=$(md vendor-modules); SNAPSHOT_URL=$(md snapshot-url || true)
R=gs://$BUCKET/runs/$RUN
LOG=/var/log/gold-build.log; STAGE=/out; SRC=/src  # not OUT: envsetup.sh sets that
exec > >(tee -a $LOG) 2>&1

status() { echo "$1" | gcloud storage cp - $R/status --quiet; }
START=$(date +%s)
say() { local t=$(( $(date +%s) - START )); printf '== +%02d:%02d:%02d %s\n' $((t / 3600)) $((t / 60 % 60)) $((t % 60)) "$*"; }
finish() {
  local rc=$?
  gcloud storage cp $LOG $R/build.log --quiet
  # What the build tools recorded about the run, for the workflow's diagnostics and summary.
  if [ -d $SRC/out ]; then
    mkdir -p /diag
    gzip -c $SRC/out/.ninja_log > /diag/ninja_log.gz 2>/dev/null
    for f in build.trace.gz error.log soong.log; do cp $SRC/out/$f /diag/ 2>/dev/null; done
    ccache -s > /diag/ccache.txt 2>/dev/null
    gcloud storage cp /diag/* $R/diag/ --quiet
  fi
  if [ $rc = 0 ] && [ -f $STAGE/done ]; then status done; else status failed; fi
}
trap finish EXIT

# Push the log every 20 seconds so the workflow can follow along.
( while sleep 20; do gcloud storage cp $LOG $R/build.log --quiet 2>/dev/null; done ) &

status running
say "run $RUN: device $DEVICE_REF, vendor $VENDOR_REF, kernel $KERNEL_REF, GOLD_GKI=$GKI, GOLD_VENDOR_MODULES=$VMODS"
nproc; free -g | sed -n 2p; df -h / | tail -1

say "build dependencies"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq bc bison build-essential ccache curl flex g++-multilib gcc-multilib git git-lfs \
  gnupg gperf imagemagick protobuf-compiler python3-protobuf lib32readline-dev lib32z1-dev libdw-dev \
  libelf-dev lz4 libsdl1.2-dev libssl-dev libxml2 libxml2-utils lzop pngcrush rsync schedtool \
  squashfs-tools xsltproc zip zlib1g-dev python-is-python3 zstd > /dev/null || exit 1
curl -sfo /usr/local/bin/repo https://storage.googleapis.com/git-repo-downloads/repo && chmod +x /usr/local/bin/repo || exit 1
git config --global user.name gold-ci; git config --global user.email gold-ci@localhost
git config --global color.ui false
git lfs install --system > /dev/null

# 64 GB is enough for Soong's analysis, but not with much room.
fallocate -l 32G /swapfile && chmod 600 /swapfile && mkswap -q /swapfile && swapon /swapfile

say "sync"
mkdir -p $SRC $STAGE; cd $SRC
RGROUPS=default
[ "$GKI" = stock ] && [ "$VMODS" = stock ] || RGROUPS=default,gold-kernel-source
repo init -q -u https://github.com/LineageOS/android.git -b lineage-24.0 --git-lfs --depth=1 -g $RGROUPS || exit 1
if [ -n "$SNAPSHOT_URL" ]; then
  curl -sfo .repo/manifests/snapshot.xml "$SNAPSHOT_URL" || exit 1
  repo init -q -m snapshot.xml || exit 1
else
  git clone -q -b lineage-24.0 https://github.com/Star-caorui/local_manifests .repo/local_manifests || exit 1
  # Put each of our repositories at the ref asked for (a branch, a tag or a commit).
  python3 - .repo/local_manifests/gold.xml "$DEVICE_REF" "$VENDOR_REF" "$KERNEL_REF" <<'EOF' || exit 1
import sys, xml.etree.ElementTree as ET
path, dev, ven, ker = sys.argv[1:]
refs = {'android_device_xiaomi_gold': dev, 'android_vendor_xiaomi_gold': ven, 'android_device_xiaomi_gold-kernel': ker}
t = ET.parse(path)
for p in t.getroot().iter('project'):
    if p.get('name') in refs:
        p.set('revision', refs[p.get('name')])
        print(p.get('name'), '->', refs[p.get('name')])
t.write(path)
EOF
fi
repo sync -c -q -j$(nproc) --no-tags --no-clone-bundle --force-sync --optimized-fetch --retry-fetches=5 || exit 1
repo manifest -r -o $STAGE/manifest-snapshot.xml || exit 1
# The commit each of our repositories is built from, for the run's summary. Uploaded before the
# "synced" line, which is what the workflow waits for to write it.
{
  [ -d .repo/local_manifests/.git ] && echo "local_manifests $(git -C .repo/local_manifests rev-parse HEAD)"
  for d in device/xiaomi/gold vendor/xiaomi/gold device/xiaomi/gold-kernel kernel/xiaomi/gold \
           kernel/xiaomi/gold-modules kernel/xiaomi/gold-mediatek_modules; do
    [ -d $d ] && echo "$(git -C $d config --get remote.$(git -C $d remote | head -1).projectname 2>/dev/null || echo $d) $(git -C $d rev-parse HEAD)"
  done
} > $STAGE/commits.txt
gcloud storage cp $STAGE/commits.txt $STAGE/manifest-snapshot.xml $R/out/ --quiet || exit 1
say "synced: $(du -sh $SRC | cut -f1)"

say "ccache"
# Kept in the bucket file by file and synced both ways, so new entries are saved every 20 minutes
# while building: a spot VM taken away halfway leaves its work for the next run.
export USE_CCACHE=1 CCACHE_EXEC=$(command -v ccache) CCACHE_DIR=/ccache
C=gs://$BUCKET/ccache-files
mkdir -p $CCACHE_DIR
gcloud storage rsync -r $C $CCACHE_DIR --quiet 2>/dev/null && say "ccache restored: $(du -sh $CCACHE_DIR | cut -f1)" || say "no ccache yet"
ccache -M 50G > /dev/null; ccache -z > /dev/null
( while sleep 1200; do gcloud storage rsync -r $CCACHE_DIR $C --quiet 2>/dev/null; done ) &

say "build"
export GOLD_GKI=$GKI GOLD_VENDOR_MODULES=$VMODS
set +u
source build/envsetup.sh
breakfast gold userdebug || exit 1
m bacon || exit 1
set -u
ccache -s | grep -E 'Hits|Misses' | head -3

say "collect"
P=$SRC/out/target/product/gold
cp $P/lineage-*-gold.zip $STAGE/package.zip || exit 1
for i in boot vendor_boot dtbo vbmeta vbmeta_system vbmeta_vendor; do cp $P/$i.img $STAGE/ || exit 1; done
prop() { grep -m1 "^$1=" $P/system/build.prop | cut -d= -f2; }
{
  echo "incremental=$(prop ro.build.version.incremental)"
  echo "lineage=$(prop ro.lineage.build.version)"
  echo "android=$(prop ro.build.version.release)"
  echo "security_patch=$(prop ro.build.version.security_patch)"
  echo "date=$(date -u +%Y-%m-%d)"
  echo "gki=$GKI"; echo "vendor_modules=$VMODS"
} > $STAGE/build-info.txt
cat $STAGE/build-info.txt
gcloud storage cp $STAGE/* $R/out/ --quiet || exit 1

say "save ccache"
gcloud storage rsync -r $CCACHE_DIR $C --quiet || say "ccache upload failed"

touch $STAGE/done
say "done"
