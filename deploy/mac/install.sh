#!/usr/bin/env bash
# Pull the server's backups to this Mac every night at 03:15 (or when it
# next wakes, if it was asleep), into ~/BioManagerBackups.
#   deploy/mac/install.sh            install or update
#   deploy/mac/install.sh --remove   stop it (the copies stay)
# Needs `ssh biomanager` to work without a prompt (key in the Keychain).
# BIOMANAGER_SSH_HOST, BIOMANAGER_SERVER_BACKUPS and BIOMANAGER_MAC_BACKUPS,
# if set when installing, are kept for the nightly run (see pull-backups.sh).
set -euo pipefail
label=org.biomanager.pull-backups
support="$HOME/Library/Application Support/BioManager"
plist="$HOME/Library/LaunchAgents/$label.plist"

launchctl bootout "gui/$(id -u)/$label" 2>/dev/null || true
if [ "${1:-}" = "--remove" ]; then
  rm -f "$plist"; echo "Removed. Copies are still in ~/BioManagerBackups."; exit 0
fi

mkdir -p "$support" "$HOME/Library/LaunchAgents"
install -m 755 "$(dirname "$0")/pull-backups.sh" "$support/pull-backups.sh"
settings=""
for name in BIOMANAGER_SSH_HOST BIOMANAGER_SERVER_BACKUPS BIOMANAGER_MAC_BACKUPS; do
  [ -n "${!name:-}" ] && settings="$settings<key>$name</key><string>${!name}</string>"
done
[ -n "$settings" ] && settings="<key>EnvironmentVariables</key><dict>$settings</dict>"
cat > "$plist" <<X
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>$label</string>
  <key>ProgramArguments</key>
  <array><string>$support/pull-backups.sh</string></array>
  <key>StartCalendarInterval</key>
  <dict><key>Hour</key><integer>3</integer><key>Minute</key><integer>15</integer></dict>
  <key>StandardOutPath</key><string>$support/launchd.log</string>
  <key>StandardErrorPath</key><string>$support/launchd.log</string>
  <key>ProcessType</key><string>Background</string>
  $settings
</dict>
</plist>
X
launchctl bootstrap "gui/$(id -u)" "$plist"
echo "Installed: runs daily at 03:15. Log: ~/BioManagerBackups/pull.log"
