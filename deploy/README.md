# Running BioManager on a lab server

One machine (a department VM or a lab-owned Linux box) runs the whole
stack in Docker:

```
browser ──HTTPS──▶ caddy ──▶ app (gunicorn) ──▶ db (PostgreSQL 16)
                                  │                  ▲
                         appdata volume              │ pg_dump
                    (uploads, signing key) ◀── backup ┘ ──▶ ./backups ──▶ restic (off-site)
```

Only Caddy listens on the network (80 and 443). The database sits on an
internal Docker network with no route out.

Keep the server **off the open internet**: on the campus network or VPN, or
a private network such as Tailscale.

## First start

On the server, with Docker and the compose plugin installed:

```bash
git clone <this repository> biomanager && cd biomanager/deploy
cp .env.example .env && chmod 600 .env
# edit .env: DOMAIN, POSTGRES_PASSWORD (openssl rand -hex 24), TZ, backups
docker compose up -d --build
docker compose logs app | grep "setup code"
```

Open `https://DOMAIN/register` and create the first account with that setup
code. It becomes the admin. Everyone else who signs up waits for an admin's
approval in Settings → Manage users.

### HTTPS

`TLS` in `.env` picks where the certificate comes from:

| `TLS=` | Use when |
| --- | --- |
| `tailscale` | The lab reaches the server over Tailscale (below). A real certificate for its `*.ts.net` name, renewed by Tailscale; nothing to install on lab machines. Also set `COMPOSE_FILE=compose.yaml:compose.tailscale.yaml`, and turn on HTTPS in the Tailscale admin console (DNS → HTTPS Certificates). |
| `internal` (default) | No public DNS name and no Tailscale. Caddy runs its own certificate authority; install its root certificate on the lab's machines once: `docker compose exec caddy cat /data/caddy/pki/authorities/local/root.crt > biomanager-root.crt` |
| `files` | IT issued a certificate. Put it in `deploy/certs/server.crt` and `server.key`. |
| `acme` | The name is in public DNS and port 80 is reachable, so Let's Encrypt can issue one for `ACME_EMAIL`. |

### Reaching it over Tailscale

The server joins your Tailscale network (`sudo tailscale up --hostname=biomanager`),
and in the admin console you **disable key expiry** for it (otherwise it drops
off after 180 days) and turn on MagicDNS and HTTPS. Lab members either join
the tailnet (free for up to 6 users) or get the one machine **shared** with
their own Tailscale account (Machines → biomanager → Share). The cloud
firewall then needs no inbound rules at all: not for 80/443, and not for SSH,
which also goes over Tailscale.

## Moving an existing lab onto the server

The SQLite database from a laptop or the desktop app is copied once,
**before the app's first start** (the app seeds an empty database when it
starts, and the copy only goes into an empty one). Instead of
`docker compose up -d --build` above:

```bash
docker compose build
docker compose up -d db
docker compose run --rm --no-deps -v /path/to/biomanager.db:/import/lab.db:ro app \
  sh -c 'python scripts/migrate-to-postgres.py /import/lab.db "$DATABASE_URL"'
docker compose up -d
```

`scripts/migrate-to-postgres.py` only reads the SQLite file. It checks that
every value fits before it writes anything, copies everything in one
transaction, keeps ids from ever being reused, and compares row counts.
`--dry-run` does all of that and then rolls back.

Uploaded files are separate. Copy them into the app volume:

```bash
docker compose cp /path/to/uploads/. app:/data/uploads/
```

The desktop app keeps them in `~/Library/Application Support/Biomanager/uploads/`;
a source checkout keeps them in `app/static/uploads/`.

## Backups

The `backup` service runs nightly at `BACKUP_TIME`, and once when it starts:

1. `pg_dump` of the database, checked with `pg_restore --list` before it is kept.
2. A tarball of the app volume: uploads, and the signing key that decrypts
   stored Google tokens.
3. The newest `KEEP_LOCAL` of each are kept in `BACKUP_DIR` (default
   `deploy/backups/`). Put that on a different disk if you can.
4. **Off-site**, if `RESTIC_REPOSITORY` is set: encrypted before it leaves,
   and kept for 30 days, 12 weeks and 24 months. Keep `RESTIC_PASSWORD`
   somewhere other than this server.
5. It pings `HEALTHCHECK_PING_URL`, if set, after every good backup. A
   service like healthchecks.io then tells you when backups **stop** — a
   failed backup can't send its own alert.

Every `RESTORE_TEST_WEEKDAY` the newest backup is restored into a scratch
database and checked. `docker compose ps` shows the backup service as
*unhealthy* when the last good backup is more than 26 hours old.

```bash
docker compose logs backup          # what ran, what it kept, restore-test results
docker compose exec backup backup.sh        # a backup now
docker compose exec backup restore-test.sh  # a restore test now
```

### Restoring

The backup files belong to root and only root can read them (they hold the
signing key), so list them through the backup service:

```bash
docker compose exec backup ls -lt /backups/db /backups/files
```

```bash
docker compose stop app
docker compose --profile restore run --rm restore \
  /backups/db/biomanager-<time>.dump /backups/files/biomanager-files-<time>.tar.gz
docker compose start app
```

Nothing is deleted. The database being replaced is renamed
`biomanager_before_<time>`, and the files being replaced are moved into
`.before-restore-<time>/` on the volume. Drop those once you are sure.

From the off-site copy, first `restic restore latest --target /somewhere`
with the same repository and password, then restore from those files.

## Updating

```bash
docker compose exec backup backup.sh     # a fresh backup first
git pull
docker compose up -d --build
docker compose logs -f app               # watch it start
```

Start-up brings the database schema up to date by itself.

## Without Docker

Everything above also works on a plain server:

- the app runs with `gunicorn -c gunicorn.conf.py wsgi:app` behind Caddy or nginx (see the main README);
- `deploy/backup/backup.sh` and `restore-test.sh` run from cron with the
  usual `PGHOST`/`PGUSER`/`PGPASSWORD`/`PGDATABASE`, `APPDATA_DIR` and `BACKUP_ROOT` set.
