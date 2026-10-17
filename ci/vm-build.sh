#!/bin/bash
# Startup script of the build VM that .github/workflows/build.yml creates. It builds one LineageOS
# package from source following local_manifests' README, puts the files in the bucket under
# runs/<run id>/ and then idles: the workflow deletes the VM as soon as it sees the status, and
# the VM's maximum run time deletes it if the workflow is gone.
#
# Instance metadata it reads: run-id, bucket, device-ref, vendor-ref, kernel-ref, gki,
# vendor-modules, snapshot-url (optional: a manifest snapshot of an earlier build to rebuild it),
# sync-only (true: stop after the sync).

set -uo pipefail
export HOME=/root  # startup scripts run without it; git and Soong need it
md() { curl -sf -H 'Metadata-Flavor: Google' "http://metadata.google.internal/computeMetadata/v1/instance/attributes/$1"; }
RUN=$(md run-id); BUCKET=$(md bucket)
DEVICE_REF=$(md device-ref); VENDOR_REF=$(md vendor-ref); KERNEL_REF=$(md kernel-ref)
GKI=$(md gki); VMODS=$(md vendor-modules); SNAPSHOT_URL=$(md snapshot-url || true)
SYNC_ONLY=$(md sync-only || true)
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

# The VM comes with local SSDs when they were to be had (cheaper than a big persistent disk, and the
# same speed for this build): one RAID 0 holds the source, the output, ccache and swap. Without them
# everything stays on the boot disk.
SWAP=/swapfile
ssds=$(ls /dev/disk/by-id/google-local-nvme-ssd-* 2>/dev/null)
if [ -n "$ssds" ]; then
  n=$(echo $ssds | wc -w); dev=$ssds
  if [ $n -gt 1 ]; then mdadm --create /dev/md0 --level=0 --raid-devices=$n $ssds --run -q || exit 1; dev=/dev/md0; fi
  mkfs.ext4 -q -F -m 0 $dev && mkdir -p /mnt/ssd && mount -o noatime $dev /mnt/ssd || exit 1
  for d in $SRC $STAGE /ccache; do mkdir -p /mnt/ssd$d $d && mount --bind /mnt/ssd$d $d || exit 1; done
  SWAP=/mnt/ssd/swapfile
fi

# For the sync's part of the summary: the time, the bytes received, the bytes written to the disk
# the source tree is on, and the CPU time spent waiting for that disk, read before and after each phase.
mkdir -p $SRC $STAGE
BOOT=$(cut -d. -f1 /proc/uptime)  # seconds from boot to this script
DISK=$(findmnt -no SOURCE --target $SRC | sed 's/\[.*//')
DISKNAME=$(basename $DISK)  # the whole disk when it is a partition; a RAID or a whole disk as it is
[ "$(lsblk -dno TYPE $DISK)" = part ] && DISKNAME=$(lsblk -dno PKNAME $DISK)
counters() {
  echo "$(date +%s)" \
    "$(awk 'NR > 2 && !/^ *lo:/ { sub(/^[^:]*:/, ""); s += $1 } END { printf "%.0f", s }' /proc/net/dev)" \
    "$(awk -v d=$DISKNAME '$3 == d { printf "%.0f", $10 * 512 }' /proc/diskstats)" \
    "$(awk '/^cpu / { printf "%.0f %.0f", $6, $2 + $3 + $4 + $5 + $6 + $7 + $8 + $9 }' /proc/stat)"
}
C0=$(counters)

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
fallocate -l 32G $SWAP && chmod 600 $SWAP && mkswap -q $SWAP && swapon $SWAP

say "sync"
# The googlesource cookie the workflow may have left in Secret Manager, kept for when an anonymous
# fetch is rate-limited: signed in, googlesource counts against the account instead of this VM's IP.
# Only then, because a signed-in fetch (through /a/) came down at 28 MB/s against 48 anonymously.
COOKIE=
if cookie=$(gcloud secrets versions access latest --secret googlesource-cookie 2>/dev/null) && [ -n "$cookie" ]; then
  (umask 077; printf '%s\n' "$cookie" | tr , '\t' > $HOME/.gitcookies); unset cookie
  git config --global http.cookiefile $HOME/.gitcookies
  COOKIE=$HOME/.gitcookies
fi
sign_in() {
  [ -n "$COOKIE" ] || return 1
  git config --global url."https://android.googlesource.com/a/".insteadOf "https://android.googlesource.com/"
  # The plain URL, which the rule above turns into /a/: what repo will fetch from.
  if err=$(git ls-remote https://android.googlesource.com/platform/build HEAD 2>&1 > /dev/null); then
    say "googlesource: signed in"
  else
    say "googlesource: the cookie was not accepted ($(echo "$err" | tail -1 | cut -c1-100))"
    git config --global --unset url."https://android.googlesource.com/a/".insteadOf
    return 1
  fi
}
C1=$(counters)
cd $SRC
# The newest .repo the bucket keeps (repo-cache/<platform security patch>/: a tar in 32 parts, made by
# fetching the default groups without checking out). With it the fetch below brings only what changed
# since; without it, or when it does not come down whole, the fetch brings everything.
CACHE=$(gcloud storage ls gs://$BUCKET/repo-cache/ 2>/dev/null | sort | tail -1)
if [ -n "$CACHE" ] && mkdir .rc && gcloud storage cp "${CACHE}*" .rc/ --quiet \
    && (cd .rc && grep ' repo\.tar\.' SHA256SUMS | xargs -P $(nproc) -L 1 sh -c 'echo "$0  $1" | sha256sum -c --quiet -') \
    && cat .rc/repo.tar.* | tar -xf -; then
  say "source cache $(basename $CACHE): $(du -sh .repo | cut -f1)"
  # For the clean-up's table of what the bucket holds.
  crev=$(grep -s '^vendor_lineage=' .rc/info.txt | cut -d= -f2)
  {
    echo "cache=$(basename $CACHE)"
    echo "cache_made=$(grep -s '^date=' .rc/info.txt | cut -d= -f2 | cut -c1-10)"
    echo "cache_vendor_lineage=$crev"
    echo "cache_commit_date=$(git --git-dir=.repo/projects/vendor/lineage.git log -1 --format=%cs $crev 2>/dev/null)"
  } > $STAGE/storage.txt
else
  [ -n "$CACHE" ] && say "source cache $(basename $CACHE) did not come down, fetching everything"
  rm -rf .repo
fi
rm -rf .rc
C1a=$(counters)
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
# Fetching and checking out apart, so the summary shows which of the two the time goes to.
# android.googlesource.com answers a busy anonymous client with HTTP 429 now and then, past repo's
# own retries. Another run fetches only the projects that failed: signed in if there is a cookie,
# otherwise a minute later. --force-sync because the source cache can have a path under another
# project than the manifest now does (local_manifests swaps a few for our forks), which repo
# otherwise refuses to replace.
for try in 1 2 3; do
  repo sync -n -c -q -j$(nproc) --no-tags --no-clone-bundle --optimized-fetch --retry-fetches=5 --force-sync && break
  [ $try = 3 ] && exit 1
  say "fetch failed"
  [ $try = 1 ] && sign_in || { say "trying again in a minute"; sleep 60; }
done
C1b=$(counters)
repo sync -l -c -q -j$(nproc) --no-tags --force-sync || exit 1
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
C2=$(counters); SIZE=$(du -sh $SRC | cut -f1)
{
  echo "synced_patch=$(cat vendor/lineage/release/flag_values/*/RELEASE_PLATFORM_SECURITY_PATCH.textproto 2>/dev/null \
    | grep -o '[0-9]\{4\}-[0-9][0-9]-[0-9][0-9]' | sort | tail -1)"
  echo "synced_vendor_lineage=$(git -C vendor/lineage rev-parse HEAD 2>/dev/null)"
  echo "synced_commit_date=$(git -C vendor/lineage log -1 --format=%cs 2>/dev/null)"
  echo "$C1a $C1b" | awk '{ printf "fetched_bytes=%.0f\n", $7 - $2 }'
} >> $STAGE/storage.txt
{
  echo "| Phase | Time | Downloaded | Download speed | Written | Write speed | I/O wait |"
  echo "| --- | --- | --- | --- | --- | --- | --- |"
  printf '| Boot | %dm %02ds | | | | | |\n' $((BOOT / 60)) $((BOOT % 60))
  for row in "Build dependencies|$C0|$C1" "Sync: source cache|$C1|$C1a" "Sync: fetch|$C1a|$C1b" "Sync: check out|$C1b|$C2"; do
    IFS='|' read name a b <<< "$row"
    echo "$a $b" | awk -v n="$name" '{
      t = $6 - $1; rx = $7 - $2; wr = $8 - $3; w = $9 - $4; all = $10 - $5
      if (t < 1) t = 1
      printf "| %s | %dm %02ds | %.1f GB | %.0f MB/s | %.1f GB | %.0f MB/s | %.0f%% |\n",
        n, t / 60, t % 60, rx / 1e9, rx / t / 1e6, wr / 1e9, wr / t / 1e6, all ? 100 * w / all : 0 }'
  done
  echo
  echo "Source tree $SIZE on \`$DISKNAME\` ($(lsblk -dno SIZE,MODEL /dev/$DISKNAME | xargs)), $(nproc) CPUs."
} > $STAGE/sync-times.md
cat $STAGE/sync-times.md
gcloud storage cp $STAGE/commits.txt $STAGE/manifest-snapshot.xml $STAGE/sync-times.md $STAGE/storage.txt $R/out/ --quiet || exit 1
say "synced: $SIZE"
[ "$SYNC_ONLY" = true ] && { touch $STAGE/done; say "done (sync only)"; exit 0; }

say "ccache"
# Kept in the bucket file by file and synced both ways, so new entries are saved every 20 minutes
# while building: a spot VM taken away halfway leaves its work for the next run.
export USE_CCACHE=1 CCACHE_EXEC=$(command -v ccache) CCACHE_DIR=/ccache
C=gs://$BUCKET/ccache-files
mkdir -p $CCACHE_DIR
# ccache drops the least recently used entries past 50 GB; the last upload drops them from the bucket
# too, but only when the whole cache came down first, so a failed download cannot empty the bucket.
PRUNE=
if gcloud storage rsync -r $C $CCACHE_DIR --quiet 2>/dev/null; then
  say "ccache restored: $(du -sh $CCACHE_DIR | cut -f1)"; PRUNE=--delete-unmatched-destination-objects
  echo "ccache_restored_bytes=$(du -sb $CCACHE_DIR | cut -f1)" >> $STAGE/storage.txt
else
  say "no ccache restored"
fi
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
# ro.lineage.* is in product/etc/build.prop, the rest in system/build.prop.
prop() { cat $P/system/build.prop $P/product/etc/build.prop | grep -m1 "^$1=" | cut -d= -f2; }
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
gcloud storage rsync -r $PRUNE $CCACHE_DIR $C --quiet || say "ccache upload failed"

touch $STAGE/done
say "done"
