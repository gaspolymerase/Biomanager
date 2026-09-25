#!/usr/bin/env bash
# Healthy while the last good backup is under 26 hours old.
f="${BACKUP_ROOT:-/backups}/last-success"
[ -f "$f" ] && [ $(( $(date -u +%s) - $(cat "$f") )) -lt 93600 ]
