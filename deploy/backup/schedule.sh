#!/usr/bin/env bash
# Run a backup at BACKUP_TIME every day (and once at start, so a broken
# configuration shows up now rather than tomorrow night), and a test restore
# on RESTORE_TEST_WEEKDAY (1 = Monday … 7 = Sunday).
set -uo pipefail
: "${BACKUP_TIME:=02:30}" "${RESTORE_TEST_WEEKDAY:=7}" "${BACKUP_ON_START:=1}"

log() { echo "[$(date -Is)] $*"; }

run_once() {
  if backup.sh; then
    if [ "$(date +%u)" = "$RESTORE_TEST_WEEKDAY" ]; then
      restore-test.sh || log "RESTORE TEST FAILED — the latest backup could not be restored"
    fi
  else
    log "BACKUP FAILED"
  fi
}

[ "$BACKUP_ON_START" = "1" ] && run_once

while true; do
  now=$(date +%s)
  next=$(date -d "today $BACKUP_TIME" +%s)
  [ "$next" -le "$now" ] && next=$(date -d "tomorrow $BACKUP_TIME" +%s)
  log "next backup at $(date -d "@$next" -Is)"
  sleep $(( next - now ))
  run_once
done
