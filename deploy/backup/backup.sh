#!/usr/bin/env bash
# One backup: the database and the app's data volume, each checked before
# it is kept; local copies pruned to KEEP_LOCAL; sent off-site when
# RESTIC_REPOSITORY is set. Works outside Docker too, with the usual
# PGHOST/PGUSER/PGPASSWORD/PGDATABASE and APPDATA_DIR set.
set -euo pipefail
: "${BACKUP_ROOT:=/backups}" "${APPDATA_DIR:=/appdata}" "${KEEP_LOCAL:=30}"
log() { echo "[$(date -Is)] $*"; }

# A dump of the wrong (or an empty) database would look like a backup.
if ! psql -XAtc "SELECT 1 FROM users LIMIT 1" > /dev/null 2>&1; then
  log "$PGDATABASE on $PGHOST has no BioManager tables — wrong database, or the app has never started. No backup taken."
  exit 1
fi

umask 077
stamp=$(date -u +%Y%m%d-%H%M%SZ)
mkdir -p "$BACKUP_ROOT/db" "$BACKUP_ROOT/files"
dump="$BACKUP_ROOT/db/biomanager-$stamp.dump"
files="$BACKUP_ROOT/files/biomanager-files-$stamp.tar.gz"

# A consistent snapshot even while people are working: pg_dump reads one
# transaction. Written under a temporary name, so a half-written file is
# never mistaken for a backup.
pg_dump --format=custom --compress=6 --no-owner --file="$dump.partial"
pg_restore --list "$dump.partial" > /dev/null   # readable, table of contents intact
mv "$dump.partial" "$dump"

tar -C "$APPDATA_DIR" --exclude="./.before-restore-*" -czf "$files.partial" .
tar -tzf "$files.partial" > /dev/null
mv "$files.partial" "$files"

log "backed up: $(basename "$dump") ($(du -h "$dump" | cut -f1)), $(basename "$files") ($(du -h "$files" | cut -f1))"

prune() {  # keep the newest KEEP_LOCAL files matching $1
  ls -1t $1 2>/dev/null | tail -n +$(( KEEP_LOCAL + 1 )) | while read -r old; do rm -f -- "$old"; done
}
prune "$BACKUP_ROOT/db/biomanager-*.dump"
prune "$BACKUP_ROOT/files/biomanager-files-*.tar.gz"

if [ -n "${RESTIC_REPOSITORY:-}" ]; then
  restic cat config > /dev/null 2>&1 || restic init
  restic backup --quiet --tag biomanager --host biomanager "$dump" "$files"
  restic forget --quiet --tag biomanager --host biomanager \
    --keep-daily 30 --keep-weekly 12 --keep-monthly 24 --prune
  log "sent off-site to $RESTIC_REPOSITORY"
fi

date -u +%s > "$BACKUP_ROOT/last-success"
if [ -n "${HEALTHCHECK_PING_URL:-}" ]; then
  curl -fsS -m 10 --retry 3 "$HEALTHCHECK_PING_URL" > /dev/null || log "could not ping $HEALTHCHECK_PING_URL"
fi
