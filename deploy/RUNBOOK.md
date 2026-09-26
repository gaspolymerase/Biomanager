# BioManager operations runbook

What to do when something happens. Each section is a checklist with the
commands to run. Setting the server up in the first place is in
[README.md](README.md).

Commands marked **server** run after `ssh biomanager` (from the admin's Mac,
over Tailscale), in the deploy folder:

```bash
ssh biomanager
cd /opt/biomanager/Biomanager/deploy
```

## Where everything is

| What | Where |
| --- | --- |
| The site | `https://biomanager.tail99374b.ts.net`, only over Tailscale |
| The server | Oracle Cloud VM `samus` (Ubuntu 24.04, ARM), Tailscale name `biomanager` |
| The code on the server | `/opt/biomanager/Biomanager`, updated by `git push server master` from the Mac |
| Settings and secrets | `/opt/biomanager/Biomanager/deploy/.env` (readable by root and `ubuntu` only) |
| Services | `db` (PostgreSQL 16), `app` (gunicorn), `caddy` (HTTPS), `backup` |
| Backups on the server | `/opt/biomanager/backups/` (root only): nightly at 02:30, 30 kept, restore-tested on Sundays |
| Backups on the Mac | `~/BioManagerBackups/db` and `files`, pulled nightly at 03:15, 30 kept, in Time Machine too |
| Backups off-site | Backblaze B2 bucket (restic, encrypted; the password is in your password manager and in `.env`), after each nightly backup |
| Alerts | the ntfy topic in `/etc/biomanager/watchdog.env` on the server; macOS notifications from the Mac job |
| Automatic jobs | watchdog every 5 min; image refresh Sundays 03:30; OS security updates nightly (reboot at 04:30 if needed) |

## An alert arrived

| Alert | What it means | Do |
| --- | --- | --- |
| **site** | `/healthz` does not answer over HTTPS | [The site is down](#the-site-is-down) |
| **containers** | a service stopped or is unhealthy | **server** `docker compose ps`, then `docker compose logs --tail 100 <service>`; `docker compose up -d` restarts anything stopped |
| **disk** | the disk is over 85% full | **server** `df -h /`, `docker system df`; `docker image prune -f` frees old images. If backups grew, lower `KEEP_LOCAL` in `.env` |
| **backup** | no good backup for 26 hours | **server** `docker compose logs backup`; run one now with `docker compose exec backup backup.sh` |
| **restore-test** | the weekly restore test has not passed for 8 days | **server** `docker compose exec backup restore-test.sh` and read what it says. Treat this as urgent: the backups may not be restorable |
| **offsite** | last night's off-site copy failed (the local backup is fine) | **server** `docker compose logs backup` names the reason: no answer from the storage, a wrong password, or a key that may not write. Run one now: `docker compose exec backup backup.sh` |
| **offsite-restore-test** | the weekly read-back from off-site has not passed for 8 days | **server** `docker compose exec backup restore-test.sh`. Urgent: the off-site copies may not be restorable |
| **certificate** | the HTTPS certificate expires within 14 days | Tailscale renews it; check HTTPS is still enabled in the Tailscale admin console (DNS), then **server** `docker compose restart caddy` |
| **tailscale** | the server left the Tailscale network | **server** (over the Oracle console's serial console if SSH is down) `sudo tailscale up` |
| **weekly update failed** | Sunday's image refresh stopped | Read the message. Nothing was updated if the backup failed. If the app is unhealthy after it, see [Updating went wrong](#updating-went-wrong) |
| Mac: **backup copy failed** | the Mac could not pull from the server | Is Tailscale on? Then `ssh biomanager` by hand; if that fails, the server is down |
| Mac: **backups have stopped** | the server's newest backup is over 48 h old | The server is up but not backing up: as **backup** above |

## The site is down

1. On your own device: is Tailscale switched on? Open `https://biomanager.tail99374b.ts.net/healthz`.
2. `ssh biomanager`. If that fails, the VM or its Tailscale is down; go to step 5.
3. **server** `docker compose ps`. Start anything not running: `docker compose up -d`.
4. **server** `docker compose logs --tail 200 app` (or `caddy`, `db`) for the error.
5. Oracle console → Compute → Instances → `samus`. If it is **Stopped**, press
   **Start**. Everything starts by itself at boot: Docker, the stack,
   Tailscale and the timers. Give it three minutes.
6. If the instance is gone, or will not boot: [The server is lost](#the-server-is-lost).

## Oracle stopped the VM

Free-tier VMs that look idle for a week may be stopped. Start it again from the
console (step 5 above); nothing is lost. Upgrading the account to Pay As You
Go stops this happening, and Always Free resources stay free.

## Restore a backup (the server is fine)

For a mistake in the data that undo in the app cannot fix. Everything since
that backup is lost, so check the time first.

```bash
# server
docker compose exec backup ls -lt /backups/db /backups/files   # pick a time
docker compose stop app
docker compose --profile restore run --rm restore \
  /backups/db/biomanager-<time>.dump /backups/files/biomanager-files-<time>.tar.gz
docker compose start app
```

The replaced database is kept as `biomanager_before_<time>` and the replaced
files in `/data/.before-restore-<time>/`. When you are sure:

```bash
# server
docker compose exec db psql -U biomanager -d postgres -c 'DROP DATABASE "biomanager_before_<time>"'
```

## The server is lost

The VM was deleted, or its disk is unreadable. Rebuild from the Mac's copy.

1. Create a new VM as in [README.md](README.md) (Ubuntu 24.04, A1 shape, the
   same SSH key), and run its setup (`deploy/cloud-init.yaml`, or the same
   steps by hand).
2. Join it to Tailscale as `biomanager` (`sudo tailscale up --hostname=biomanager`),
   and **delete the old `biomanager` machine** in the Tailscale admin console
   first, so the new one gets the name. Disable its key expiry.
3. From the Mac: `ssh-keygen -R biomanager.tail99374b.ts.net`, then push the code:
   `git push server master` (after creating `/opt/biomanager/Biomanager` with
   `git init` and `git config receive.denyCurrentBranch updateInstead`, as the first time).
4. **server** write `.env` again. Use the same `DOMAIN`, a new `POSTGRES_PASSWORD`,
   and leave `SECRET_KEY` empty (the restored files bring the old key back).
5. **server** `docker compose up -d --build`, wait for it to be healthy, then copy
   the newest backup up from the Mac and restore it:

   ```bash
   # Mac
   scp ~/BioManagerBackups/db/<newest>.dump ~/BioManagerBackups/files/<newest>.tar.gz biomanager:/tmp/
   # server
   sudo mv /tmp/biomanager-*.dump /opt/biomanager/backups/db/
   sudo mv /tmp/biomanager-files-*.tar.gz /opt/biomanager/backups/files/
   docker compose stop app
   docker compose --profile restore run --rm restore /backups/db/<newest>.dump /backups/files/<newest>.tar.gz
   docker compose start app
   ```
   **If the Mac's copy is gone too**, restore from off-site. Put the same
   `RESTIC_REPOSITORY`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` and
   `RESTIC_PASSWORD` (from your password manager) in the new `.env`, then:

   ```bash
   # server
   docker compose up -d --force-recreate backup
   docker compose exec backup restic snapshots                 # the copies there
   docker compose exec backup restic restore latest --tag biomanager --target /backups/from-offsite
   docker compose exec backup sh -c 'ls /backups/from-offsite/backups/db /backups/from-offsite/backups/files'
   docker compose stop app
   docker compose --profile restore run --rm restore \
     /backups/from-offsite/backups/db/<name>.dump /backups/from-offsite/backups/files/<name>.tar.gz
   docker compose start app
   ```
6. **server** `sudo deploy/host/install.sh` for the watchdog and weekly
   update (it keeps the existing ntfy topic only if you copy
   `/etc/biomanager/watchdog.env` back; otherwise subscribe to the new one).
7. Check you can sign in, then run a restore test: `docker compose exec backup restore-test.sh`.

## Moving to another server

The same as [The server is lost](#the-server-is-lost), but take a fresh
backup first (`docker compose exec backup backup.sh`), pull it to the Mac
(`~/Library/Application\ Support/BioManager/pull-backups.sh`), and stop the
old app (`docker compose stop app`) so nobody writes to it meanwhile.

## An admin is locked out

- Another admin resets their password in **Settings → Manage users**.
- No other admin can sign in:

  ```bash
  # server
  docker compose exec app python scripts/reset-password.py            # list accounts
  docker compose exec app python scripts/reset-password.py NAME --admin --enable
  ```

  It asks for the new password twice; nothing lands in the shell history.

## Someone joins

1. Tailscale admin console → Machines → `biomanager` → **Share**, and send the
   invite to them (sharing gives them this machine only).
2. Send them the lab access guide.
3. When they sign up, approve them in **Settings → Manage users**.

## Someone leaves

1. **Settings → Manage users** → **Disable**. They are signed out at once.
2. **Colony overview** (`/admin/colony`): reassign their cages and animals.
3. Tailscale admin console: revoke the machine share (or remove them from the tailnet).
4. If they were an admin, check who else is. Keep at least two.

## Updating the app

From the Mac, with the change committed:

```bash
scripts/test.sh                         # the suite passes
git push server master
ssh biomanager 'cd /opt/biomanager/Biomanager/deploy && docker compose exec -T backup backup.sh && docker compose up -d --build'
curl -fsS https://biomanager.tail99374b.ts.net/healthz
```

Start-up brings the database schema up to date by itself.

### Updating went wrong

The backup taken just before is the newest in `/backups/db`. Put the previous
code back and rebuild, then, only if the data was changed badly, restore that
backup:

```bash
git revert <bad commit> && git push server master     # Mac
docker compose up -d --build                          # server
```

## Letting a guest in from the internet

For someone outside the lab (a collaborator, a friend taking a look), for a
few days:

1. In BioManager: account menu → **Guests**. Enter who it is for and how
   long, then **Make a code**. The code is shown once; the guest gets a
   member account of their own that stops working when the pass ends.
2. On the server, put BioManager on the internet (Tailscale Funnel):

   ```bash
   ssh -t biomanager sudo /opt/biomanager/Biomanager/deploy/host/internet-access.sh on
   ```

   The first time, Tailscale prints a link to allow Funnel for this machine:
   open it, allow it, run the command again.
3. Send the guest `https://biomanager.tail99374b.ts.net:8443/guest` and the
   code. From the internet, anyone not signed in sees only that code page:
   no sign-in or sign-up form.
4. When they are done: **End now** on the Guests page, and

   ```bash
   ssh -t biomanager sudo /opt/biomanager/Biomanager/deploy/host/internet-access.sh off
   ```

What a guest adds stays, under their `guest-…` account.

## Rotating secrets

| Secret | How | What people notice |
| --- | --- | --- |
| `SECRET_KEY` (or `/data/secret_key`) | set a new value in `.env`, `docker compose up -d` | everyone signs in again; Google Calendar links must be reconnected |
| `POSTGRES_PASSWORD` | **server** `docker compose exec db psql -U biomanager -d postgres -c "ALTER USER biomanager PASSWORD '<new>'"`, put `<new>` in `.env`, `docker compose up -d` | nothing |
| Microsoft client secret | it expires on the date shown in Entra; create a new one, put it in `.env`, `docker compose up -d` before the old one expires | "Sign in with Microsoft" fails after expiry |
| Google client secret | Google Cloud → Credentials → the client → add a secret, update `.env`, then delete the old one | nothing |
| ntfy topic | edit `/etc/biomanager/watchdog.env` on the server, subscribe to the new topic | nothing |
| Backblaze key | create a new application key (this bucket, read and write), run `offsite-setup.sh` again with it, then delete the old key in Backblaze | nothing |
| Backup password | not rotated in place: it encrypts every stored copy. To change it, `docker compose exec backup restic key add`, then `restic key remove` the old one, and update `.env` and your password manager | nothing |
| The Mac's SSH key | `ssh-keygen -t ed25519 -f ~/.ssh/biomanager_oci`, put the new `.pub` in the server's `~/.ssh/authorized_keys`, remove the old line | nothing |

## Checking on it by hand

```bash
curl -fsS https://biomanager.tail99374b.ts.net/healthz           # the app and database
ssh biomanager 'cd /opt/biomanager/Biomanager/deploy && docker compose ps'
ssh biomanager 'sudo journalctl -u biomanager-watchdog --since today --no-pager -o cat'
ssh biomanager 'systemctl list-timers "biomanager-*" --no-pager'
tail ~/BioManagerBackups/pull.log                                 # the Mac's copy
```
