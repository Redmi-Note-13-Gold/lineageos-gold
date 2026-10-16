#!/bin/bash
# Follows the build VM's log in the bucket, showing the steps, the build's progress and every error
# as they come. Starts at byte <from> and returns once a line matches <until> (or, without one,
# once the VM reports it is done); fails if the VM reports a failure or is gone. Writes the byte it
# got to as pos=<n> to $GITHUB_OUTPUT, so a later job can carry on from there.
#
# Usage: ci/follow-log.sh <from> [<until>]

set -uo pipefail
R=gs://$BUCKET/runs/$GITHUB_RUN_ID
pos=$1; until=${2:-}
trap 'echo "pos=$pos" >> "$GITHUB_OUTPUT"' EXIT
: > build.log
while :; do
  sleep 20
  # Only the bytes added since the last look.
  gcloud storage cat -r $pos- $R/build.log > new.log 2>/dev/null || : > new.log
  if [ -s new.log ]; then
    cat new.log >> build.log
    pos=$((pos + $(stat -c %s new.log)))
    tr '\r' '\n' < new.log | awk '
      /^\[ *[0-9]+% / { last = $0; next }
      /^== |FAILED:|[Ee]rror[: ]|^ninja: |^#### |^fatal: |^\*\* |not found/ { print; next }
      END { if (last != "") print substr(last, 1, 160) }'
    [ -n "$until" ] && grep -aqE "$until" new.log && exit 0
  fi
  case "$(gcloud storage cat $R/status 2>/dev/null || true)" in
    done) exit 0 ;;
    failed) tail -n 60 build.log; exit 1 ;;
  esac
  # A failed lookup is not taken as the VM being gone; only an answer without it is.
  if vm=$(gcloud compute instances list --project $PROJECT --filter "name=gold-build-$GITHUB_RUN_ID" \
      --format 'value(name)' 2>/dev/null) && [ -z "$vm" ]; then
    echo "The VM is gone (spot reclaimed?)" >&2; tail -n 30 build.log; exit 1
  fi
done
