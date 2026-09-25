#!/usr/bin/env bash
# Prove the newest backup can be restored: load it into a scratch database,
# check the tables have rows, check the files archive reads, then drop the
# scratch copy. An untested backup is a hope, not a backup.
set -euo pipefail
: "${BACKUP_ROOT:=/backups}"
log() { echo "[$(date -Is)] $*"; }

dump=$(ls -1t "$BACKUP_ROOT"/db/biomanager-*.dump | head -n 1)
files=$(ls -1t "$BACKUP_ROOT"/files/biomanager-files-*.tar.gz | head -n 1)
scratch="biomanager_restore_test"

dropdb --if-exists "$scratch"
createdb "$scratch"
trap 'dropdb --if-exists "$scratch"' EXIT

pg_restore --no-owner --exit-on-error --dbname="$scratch" "$dump"

# Every table the live database has must come back, and a table that has
# rows now must not come back empty. (Counts can differ a little: people
# keep working after the dump was taken.)
live_tables=$(psql -XAtc "SELECT count(*) FROM pg_tables WHERE schemaname = 'public'")
restored_tables=$(psql -XAtd "$scratch" -c "SELECT count(*) FROM pg_tables WHERE schemaname = 'public'")
if [ "$restored_tables" -lt "$live_tables" ]; then
  log "restored database has $restored_tables tables, the live one $live_tables"
  exit 1
fi
report=""
for table in users mice strains plasmids organisms audit_log; do
  live=$(psql -XAtc "SELECT count(*) FROM $table")
  restored=$(psql -XAtd "$scratch" -c "SELECT count(*) FROM $table")
  if [ "$live" -gt 0 ] && [ "$restored" -eq 0 ]; then
    log "$table has $live rows but none in the restored copy"
    exit 1
  fi
  report="$report $table=$restored/$live"
done
tar -tzf "$files" > /dev/null

date -u +%s > "$BACKUP_ROOT/last-restore-test"
log "restore test passed for $(basename "$dump") (restored/live:$report)"
