#!/usr/bin/env bash
# Install the watchdog and weekly maintenance timers on the server, from the
# deploy folder:
#   sudo host/install.sh
# Creates /etc/biomanager/watchdog.env with a private ntfy topic the first
# time; subscribe to that topic in the ntfy app to get the alerts.
set -euo pipefail
[ "$(id -u)" = 0 ] || { echo "run with sudo"; exit 1; }
here=$(cd "$(dirname "$0")" && pwd)
chmod 755 "$here/watchdog.sh" "$here/maintenance.sh"
install -m 644 "$here"/biomanager-*.service "$here"/biomanager-*.timer /etc/systemd/system/
mkdir -p /etc/biomanager
if [ ! -f /etc/biomanager/watchdog.env ]; then
  umask 077
  cat > /etc/biomanager/watchdog.env <<X
# Alerts: subscribe to this topic in the ntfy app (ntfy.sh). Anyone who knows
# the name can read and post to it, so it is long and random; alerts never
# contain lab data. Empty it to send nothing.
NTFY_TOPIC=biomanager-$(openssl rand -hex 12)
#NTFY_SERVER=https://ntfy.sh
#DISK_LIMIT_PERCENT=85
#BACKUP_MAX_HOURS=26
X
fi
# Where this stack is, so the watchdog reads its .env (and BACKUP_DIR) wherever it was unpacked.
grep -q '^DEPLOY_DIR=' /etc/biomanager/watchdog.env || echo "DEPLOY_DIR=$(dirname "$here")" >> /etc/biomanager/watchdog.env
systemctl daemon-reload
systemctl enable --now biomanager-watchdog.timer biomanager-maintenance.timer
. /etc/biomanager/watchdog.env
echo "Installed. Alerts go to ntfy topic: ${NTFY_TOPIC:-<none>}"
systemctl list-timers 'biomanager-*' --no-pager
