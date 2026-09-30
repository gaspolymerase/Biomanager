#!/usr/bin/env bash
# Turn on off-site backups, on the server, in your own terminal:
#
#   ssh -t biomanager sudo /opt/biomanager/Biomanager/deploy/host/offsite-setup.sh
#
# Asks for the storage (any S3-compatible service: Backblaze B2, AWS S3,
# Wasabi, MinIO) and its key; the secret is not echoed and never lands in
# shell history. Creates the backup password the first time and shows it
# once, to save somewhere other than this server. Writes them to .env,
# restarts the backup service, takes a backup and restores it back from
# off-site to prove the whole path works.
#
# Run it again to change the key or the storage; the password is kept.
set -euo pipefail

DEPLOY_DIR=${DEPLOY_DIR:-/opt/biomanager/Biomanager/deploy}
ENV_FILE="$DEPLOY_DIR/.env"
[ "$(id -u)" = 0 ] || { echo "Run it with sudo."; exit 1; }
[ -f "$ENV_FILE" ] || { echo "No $ENV_FILE: set the server up first (deploy/README.md)."; exit 1; }

# As docker compose reads it: a trailing "# comment" and quotes are not the value.
get() { grep -E "^$1=" "$ENV_FILE" | tail -n 1 | cut -d= -f2- \
          | sed -E 's/[[:space:]]+#.*$//; s/^"(.*)"$/\1/; s/^'"'"'(.*)'"'"'$/\1/; s/[[:space:]]+$//' || true; }
put() {  # KEY VALUE: replace that line or add it, keeping the file's owner and mode
  local tmp
  tmp=$(mktemp "$ENV_FILE.XXXXXX")
  KEY="$1" VALUE="$2" awk 'BEGIN { k = ENVIRON["KEY"]; v = ENVIRON["VALUE"]; done = 0 }
    index($0, k "=") == 1 { if (!done) { print k "=" v; done = 1 } ; next }
    { print }
    END { if (!done) print k "=" v }' "$ENV_FILE" > "$tmp"
  chown --reference="$ENV_FILE" "$tmp"
  chmod --reference="$ENV_FILE" "$tmp"
  mv "$tmp" "$ENV_FILE"
}
ask() { local answer; read -r -p "$1" answer; printf '%s' "$answer"; }
ask_secret() { local answer; read -r -s -p "$1" answer; echo >&2; printf '%s' "$answer"; }

cat <<'X'
Off-site backups for BioManager
===============================
The storage should be an S3-compatible bucket that only this server writes
to. For Backblaze B2 the repository looks like
    s3:https://s3.us-east-005.backblazeb2.com/your-bucket-name/biomanager
(the host is the bucket's "Endpoint" on its details page).

X
current=$(get RESTIC_REPOSITORY)
repo=$(ask "Repository${current:+ [$current]}: ")
repo=${repo:-$current}
case "$repo" in
  s3:https://*) ;;
  s3:*) echo "Use an https:// endpoint, so the copies are encrypted in transit too."; exit 1 ;;
  "") echo "Nothing changed."; exit 0 ;;
  *) echo "Only S3-compatible storage (s3:https://…) is set up by this script; for others edit .env and compose.yaml."; exit 1 ;;
esac

key_id=$(ask "Key ID (Backblaze: keyID; AWS: access key ID)${current:+ [keep current]}: ")
secret=$(ask_secret "Application key / secret access key (not shown)${current:+ [keep current]}: ")
if [ -z "$(get AWS_ACCESS_KEY_ID)" ] && { [ -z "$key_id" ] || [ -z "$secret" ]; }; then
  echo "Both the key ID and the secret are needed."; exit 1
fi

password=$(get RESTIC_PASSWORD)
if [ -z "$password" ]; then
  password=$(openssl rand -hex 32)
  cat <<X

The off-site copies are encrypted with this backup password:

    $password

Save it in your password manager now, somewhere other than this server.
Without it the off-site copies cannot be read, and on the day this server
is gone, it is the one thing that has to survive.
X
  confirm=$(ask "Type saved once it is saved: ")
  [ "$confirm" = saved ] || { echo "Nothing changed. Run this again when you are ready."; exit 1; }
fi

put RESTIC_REPOSITORY "$repo"
[ -n "$key_id" ] && put AWS_ACCESS_KEY_ID "$key_id"
[ -n "$secret" ] && put AWS_SECRET_ACCESS_KEY "$secret"
put RESTIC_PASSWORD "$password"
unset secret password

cd "$DEPLOY_DIR"
echo
echo "Restarting the backup service; it takes a backup and sends it off-site as it starts…"
since=$(date -u +%Y-%m-%dT%H:%M:%SZ)
docker compose up -d --force-recreate backup > /dev/null 2>&1
# Follow that start-up backup rather than starting a second one beside it
# (two restic runs on one repository would trip over each other's lock).
for _ in $(seq 1 100); do
  docker compose logs --since "$since" backup 2>/dev/null | grep -q "next backup at" && break
  sleep 3
done
log=$(docker compose logs --no-log-prefix --since "$since" backup 2>/dev/null | grep -v NOTICE)
echo "$log" | grep -E "backed up|off-site|OFF-SITE|cannot open|creating" | sed 's/^/  /'
if ! echo "$log" | grep -q "sent off-site"; then
  echo
  echo "The off-site copy did not work (see above). Check the repository address,"
  echo "the key, and that the key may write to that bucket, then run this again."
  exit 1
fi

echo "Reading it back from off-site…"
docker compose exec -T backup restore-test.sh < /dev/null 2>&1 | grep -v NOTICE | sed 's/^/  /'
docker compose exec -T backup restic snapshots --compact < /dev/null | tail -n 4
echo
echo "Off-site backups are on: every night after the local backup, restored back every week."
