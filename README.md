# BioManager

**One place for a biology lab's living things and the stuff around them:
mice, zebrafish, flies, worms, plasmids, samples, orders, reagents,
the calendar and the lab notebook.**

BioManager replaces the pile of spreadsheets, whiteboards and paper cage
cards most labs run on. You edit records the way you would in a
spreadsheet, but underneath is a real database. It knows which mouse is in
which cage, when a litter needs weaning, which fly vials need flipping and
which antibody is about to expire, and every morning it tells you what
needs attention.

It runs as a **desktop app** for one person, or on a **lab server** that
the whole lab signs in to from a browser, including on their phones at the
rack.

---

## Contents

- [Who it's for](#who-its-for)
- [What you can track](#what-you-can-track)
- [Features across the app](#features-across-the-app)
- [Ways to run it](#ways-to-run-it)
- [Getting started](#getting-started)
- [How to use it: a first week](#how-to-use-it-a-first-week)
- [Keyboard shortcuts](#keyboard-shortcuts)
- [Accounts, permissions and privacy](#accounts-permissions-and-privacy)
- [Your data and backups](#your-data-and-backups)
- [Documentation](#documentation)
- [Credits](#credits)

---

## Who it's for

- **Lab members** who manage their own mouse lines, fish, stocks or
  samples and are tired of hunting through someone else's spreadsheet.
- **Lab managers and PIs** who need a census that is actually complete:
  who owns what, which cages are idle, what is overdue.
- **Labs with more than one organism.** Mice and zebrafish have dedicated
  modules, flies and worms have their own vial and plate databases, and
  any other organism gets a database you configure in a few clicks.

## What you can track

### Mouse colony

The most complete module, built around how a mouse room actually works.

- **Mice**: a spreadsheet of every animal with ID, sex, date of birth,
  strain, genotype, cage, owner, experiment and notes. IDs are assigned for
  you, in order, and never reused. A mouse is alive until it has a date of
  death, and a live dot shows which is which.
- **Cages**: a sheet of every cage with its rack and position, purpose,
  owner, the mice inside (with the sex breakdown), litter born and the P21
  weaning date. Expand a cage to edit its mice right there.
- **Litters**: record a birth once, and the pups' date of birth, weaning
  date (P21) and genotyping date (about P28) follow from it.
- **Breeders**: breeding cages at a glance, with breeders past 30 weeks
  flagged.
- **Strains**: your lab's lines, with owners.
- **Experiments**: put a group of mice under one experiment with a shared
  treatment group.
- **Racks**: a grid of every rack showing which positions are filled.

### Zebrafish

Lines, tanks, individual fish, clutches, matings (and returning the
fish afterwards), water systems with water-quality logs, and a sac log.
Tanks can hold a group with a headcount or resolve into named individuals.

### Drosophila and C. elegans

Vial (fly) and plate (worm) databases, organised into racks and
incubators.

- Label each vial with genotype and purpose: stock, experiment, cross or
  progeny.
- **Set crosses**, collect eggs or pick progeny into new vials, and see
  when the progeny will be adults.
- **Flip / chunk schedules that depend on temperature**, e.g. flip every
  14 days at 25 °C and every 28 at 18 °C.
- Frozen-stock records for worms.

### Any other organism: build your own database

Pick **Add database** in the sidebar, start from a preset or a blank
sheet, and describe your organism:

- **The words it uses**: cage, tank, vial or plate; strain, line or stock;
  litter, clutch or progeny. The interface then uses your words.
- **How it is counted**: individual animals, groups with a headcount, or
  both.
- **What it needs**, chosen from a checklist: crosses, cohorts, a nursery
  stage, genotyping, environment logs, cryo inventory, census and more.
- **Schedules**, such as "wean at P21", which can vary with rearing
  temperature.
- **Your own columns**: text, numbers, dates, dropdowns, people or links.

No programming is needed, and existing data is untouched.

### Plasmids

Upload a GenBank or FASTA file and BioManager stores the sequence and its
features and shows an interactive plasmid map. Plasmid boxes sit on
the same rack grid as everything else, so you can see where each tube is
kept.

### Lab inventories: samples, orders, reagents, antibodies

Every inventory runs on the same engine, starting from a preset you can
change:

| Preset | Tracks |
| --- | --- |
| **Samples** | harvested tissue and material, linked to the animal it came from, where it is stored (RT / 4 °C / −20 °C / −80 °C / LN₂) and in which box position |
| **Orders** | a status board from *requested* to *ordered* to *received*, with vendor, catalogue number, price and grant account |
| **Reagents** | quantity, concentration, CAS number, hazard, supplier and lot, and expiry dates with warnings for expired and expiring-soon items |
| **Antibodies** | host, clonality, clone, conjugate, reactivity, applications, dilution, RRID, and where each vial is stored |
| **Custom** | whatever you define |

Each inventory can separate **your own stock** from **lab common stock**,
and you can rename statuses and categories without losing items.

### Calendar and tasks

An experiment calendar with to-dos. It can show your **Google Calendar**
and any **ICS subscription** alongside lab events.

### Lab notebook

Notebook pages organised in tabs, with reusable templates, images and file
attachments. A page can link to animals and calendar events, so the
record and the notes point at each other.

### Utilities

Molecular-weight reference data and a concentration-to-mass calculator.

---

## Features across the app

**A home page that tells you what to do today.** It shows the mice
older than 30 weeks, upcoming weanings, the genotyping queue, fly and worm
vials due for flipping, expiring and low stock, zebrafish tasks, the next
14 days of the calendar and recent orders.

**Spreadsheet-style editing.** Click a cell and type. Changes save as you
go, and every table can be sorted, filtered, exported to CSV and printed.

**Add many at once.** Describe one mouse and say how many
(`4 females, 2 males`), or upload a CSV. BioManager shows an editable
preview, including the IDs it will assign, before anything is saved. Mice,
tanks, vials, plasmids and inventory items all support this.

**Batch actions with undo.** Tick rows and act on all of them together:
set a field, add them to an experiment, or sac them. Every bulk action is
recorded and **can be undone**. BioManager refuses to undo something if
someone has changed those records since, so their edits are never
silently thrown away.

**Racks and positions the way your lab labels them.** `D7`, `4-7`, `7D`,
`G12` or plain 1 to 80. Each rack keeps its own naming scheme, and a grid
shows what is where.

**Cage cards with QR codes.** Print correctly sized cards for cages,
tanks and vials. Scanning the code at the rack opens that record on your
phone, so nobody has to walk back to a computer to type an ID.

**Works on phones.** Controls are sized for fingers and pages don't zoom
when you tap, so you can check or edit a cage from the animal room.

**Search everything.** Press `Cmd/Ctrl + K` from anywhere.

**Tabs.** Every page you open becomes a tab you can reorder, and your tabs
are still there when you come back.

**Full change history.** Every create, edit and delete is recorded with who
made it and exactly what changed (`genotype: DBH-Cre → ∅`). Admins can read
the whole history.

**Daily reminder emails.** Each person can get a digest of what is
overdue or coming up for their animals, stocks and tasks. This is
optional.

**Sign in with Google or Microsoft**, or with a BioManager password. This
is optional too.

**Looks at home on a Mac.** The interface follows macOS conventions and has
a full dark mode, and it works in any modern browser on Windows and Linux.

---

## Ways to run it

| | Desktop app | Lab server | From source |
| --- | --- | --- | --- |
| **For** | one person, one computer | a whole lab, from any browser | developers |
| **Database** | SQLite, on your computer | PostgreSQL | SQLite (or PostgreSQL) |
| **Setup** | download and open | Docker on a Linux machine or VM | Python 3.11+ and Node |
| **Backups** | `dbtool.py backup` | automatic, nightly, tested weekly, optional off-site copy | `dbtool.py backup` |
| **Phones and QR codes** | no, only your computer can reach it | yes | on your local network |

You can start with the desktop app and move to a server later:
`scripts/migrate-to-postgres.py` moves an existing database across.

---

## Getting started

### Desktop app

1. Download BioManager for your system from the **Download** page, or build
   it yourself (below).
2. **macOS**: open the `.dmg` or `.zip` and drag BioManager into
   Applications. The first time, **right-click the app and choose Open**.
   macOS asks once because the app is not yet signed through the App Store.
3. Create your account. The first account on a computer becomes the admin.

Your data is kept outside the app, so updating or reinstalling never
touches it:

| System | Data folder |
| --- | --- |
| macOS | `~/Library/Application Support/Biomanager/` |
| Windows | `%APPDATA%\Biomanager\` |
| Linux | `~/.local/share/Biomanager/` |

To build the desktop app yourself:

```bash
./scripts/build-desktop.sh
open dist/BioManager.app
```

### Lab server

The supported setup is the Docker stack in [`deploy/`](deploy/README.md).
It includes HTTPS, PostgreSQL, and a backup service that dumps the
database every night, checks each dump, and test-restores one every week.

```bash
git clone <this repository> biomanager && cd biomanager/deploy
cp .env.example .env && chmod 600 .env     # set DOMAIN, POSTGRES_PASSWORD, TZ
docker compose up -d --build
docker compose logs app | grep "setup code"
```

Open `https://<your domain>/register` and create the first account using
the **setup code** from the log. That account becomes the admin.

Keep the server off the open internet. Put it on the campus network, VPN
or a private network such as Tailscale, which `deploy/README.md` covers
step by step. [`deploy/RUNBOOK.md`](deploy/RUNBOOK.md) says what to do when
something goes wrong.

### From source

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
(cd frontend && npm install && npm run build:css)
PORT=5055 python run.py
```

Open <http://127.0.0.1:5055>. (On macOS, port 5000 is taken by AirPlay,
which is why the example uses 5055.) The first account needs the setup code
printed in the terminal.

---

## How to use it: a first week

A walk-through for a mouse colony. The other modules work the same way.

**Day 1: set up.**
1. Sign in as the admin. Other lab members register, and you approve them
   in **Settings → Manage users**.
2. Open **Mouse colony → Racks** and add your racks. Choose how positions
   are labelled (`D7`, `4-7`, 1 to 80…) to match the stickers on the real
   racks.
3. Add your lines under **Strains**.

**Day 2: bring the mice in.**
1. On **Mice**, choose **Add many**. Either describe a group (`4 females,
   2 males`, strain, date of birth, cage `new`) or upload your old
   spreadsheet as a CSV. Headers like `sex`, `dob`, `cage` and `notes` are
   recognised, and other columns are ignored.
2. Check the preview grid. Fix anything, use **Fill down** for repeated
   values, and tick **Skip** for rows you don't want. Then save.
3. Open **Cages** and give each cage a purpose and a rack position.

**Day 3: label the rack.**
Select cages and choose **Print cage cards**. Put a card on each cage.
From now on, scanning a card with a phone opens that cage.

**Every morning: open Home.**
It lists the weanings due, the genotyping queue, breeders getting old and
anything else overdue. Click an item to go straight to it.

**When a litter is born:**
Open the breeding cage and record the birth. The weaning and genotyping
dates appear on Home when they come due. At weaning, add the pups with
**Add many** and move them to their new cages.

**When an experiment starts:**
Tick the mice on **Mice**. In the bar that appears at the bottom, choose
**Add to experiment** and give the treatment group. Shift-click selects a
range.

**When you make a mistake:**
Open **Batches** in the sidebar and undo the bulk action. For a single
edit, the change history shows what the value used to be.

**When you need a new kind of database:**
Choose **Add database**, pick a preset (Drosophila, C. elegans,
zebrafish, mouse) or start blank, name things your way and choose what it
needs to track.

---

## Keyboard shortcuts

| Keys | Does |
| --- | --- |
| `Cmd/Ctrl + K` | Search everything |
| `Cmd/Ctrl + B` | Show or hide the sidebar |
| `Alt + 1…9` | Switch to tab 1 to 9 |
| `Alt + ←` / `Alt + →` | Previous / next tab |
| `Alt + W` | Close the current tab |
| Middle-click a tab | Close it |
| Shift-click a row | Select a range |

---

## Accounts, permissions and privacy

- **The first account is the admin.** On a server it needs the setup code,
  so nobody else on the network can claim it first.
- **New sign-ups wait for approval** from an admin.
- **You can edit what you own.** Your mice, cages and records are yours to
  change. **Breeder cages and anything marked shared belong to the whole
  lab.** Admins can change anything.
- **Everyone can see everything**, because a census with holes is not a
  census. The **My colony / Shared / Everyone** switch filters what you see
  without changing who may edit what.
- **When someone leaves**, the admin's **Colony overview** shows every cage
  by owner, idle cages and living mice without a cage. The **Racks & boxes**
  page hands their racks to someone else.
- Passwords are at least 12 characters, repeated failed sign-ins are locked
  out, and changing a password signs out every other session.
- Everything stays on your computer or your lab's server. BioManager
  sends nothing anywhere unless you connect Google Calendar, Google or
  Microsoft sign-in, or reminder emails.

---

## Your data and backups

**Don't keep the database in a cloud-synced folder** (OneDrive, Dropbox,
Google Drive, iCloud Drive). Syncing corrupts SQLite files. BioManager
warns you at startup if it spots this.

On a single computer:

```bash
python scripts/dbtool.py check                      # where the data is, is it healthy, is it at risk
python scripts/dbtool.py backup                     # a consistent snapshot; keeps the last 30
python scripts/dbtool.py relocate ~/BioManagerData  # move it somewhere safe
python scripts/dbtool.py restore <file>
```

A lab server backs itself up every night, checks every backup, and
test-restores one every week. It can also keep a copy off-site and a
nightly copy on the admin's Mac. **Settings → Export my data** downloads
your own records as a zip at any time.

---

## Documentation

| Document | For |
| --- | --- |
| [`deploy/README.md`](deploy/README.md) | Setting up a lab server: HTTPS, Tailscale, Google/Microsoft sign-in, backups, updates |
| [`deploy/RUNBOOK.md`](deploy/RUNBOOK.md) | Running a lab server: alerts, outages, restores, people joining and leaving |
| [`docs/GOOGLE_CALENDAR_SETUP.md`](docs/GOOGLE_CALENDAR_SETUP.md) | Connecting Google Calendar |
| [`docs/DEVELOPMENT.md`](docs/DEVELOPMENT.md) | How BioManager is built: stack, styling, icons, the organism engine, access control, audit and undo, tests, security settings |

To work on BioManager itself, start with
[`docs/DEVELOPMENT.md`](docs/DEVELOPMENT.md). The test suite runs on SQLite
and PostgreSQL with `scripts/test.sh`, and runs on every push.

---

## Credits

Built with Python, Flask, SQLAlchemy, PostgreSQL / SQLite and Tailwind CSS.

Icons come from [Font Awesome Free](https://fontawesome.com) (CC BY 4.0)
and [game-icons.net](https://game-icons.net) by Delapouite (CC BY 3.0).
The mouse and fly icons are theirs. Plasmid, petri dish, cage, tank and
culture-vial icons are drawn for this project.
