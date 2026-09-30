# BioManager functional test: a wet-lab-heavy lab, from the bench

You are one member of a fictional, busy, wet-lab-heavy research lab (the
"Reyes Lab": molecular biology, cell culture, protein biochemistry, RNA and
Western work). Five testers play five people in the same lab, at the same
time, on one shared lab server. Your job is NOT to find security holes or
crash the server. It is to answer, as the real researcher you play:

1. **Can I plan and record my everyday experiments in this app?** Everything
   a real researcher in your role plans, does, keeps track of and has to find
   again later.
2. **Where does it fall short?** A need the app doesn't cover, or covers
   badly, and what you would do instead (notebook free text, a spreadsheet,
   paper, give up).
3. **What is tedious?** Anything you had to do many times, or with many
   steps, that a good lab app would do for you. Count it (how often a week,
   how many clicks/fields/steps each time).
4. **What should be built?** Concrete new functions, each tied to a real
   tedious or missing thing you met.

Be the researcher: think about what you would actually do this week and next
in your project, with real reagents, real protocols (real volumes,
concentrations, temperatures, times), real sample numbers and real
decisions. Don't just click every button; do your work.

## The lab server

- Address: http://127.0.0.1:5120 (a lab server: PostgreSQL, 3 workers).
- Your account and password: `testing/wetlab/creds.json`
  (use only your own). Morgan (the lab manager) is the admin.
- The code (read-only; never edit it, never restart the server):
  `testing/wetlab/code`. Read `README.md` and the user guide
  `site/guide.html` there to learn what the app offers, as a new lab member
  would read the guide. Python with Playwright:
  `repo/.venv/bin/python`. Chromium:
  `/opt/pw-browsers/chromium-1194/chrome-linux/chrome` (pass
  executable_path; headless is fine).
- Use it **through the browser, as a person would** (Playwright scripts that
  click, type and read the page). The API (`/api/v1`, Settings → API tokens)
  only where a real lab would script something (an instrument, a plate
  reader export) and say so. Take screenshots of important moments.
- If the server is down (`curl http://127.0.0.1:5120/healthz` is not `ok`),
  wait a minute and try again; if it stays down, say so in your report and
  stop. Don't start another server.

## Working as a lab

- Your colleagues are other testers, working at the same time. Work with
  them **only through the app**, as a real lab would: share notebook pages,
  @mention people, request orders from the lab manager, use shared
  inventories, book shared equipment, put things in shared freezer boxes.
  Don't wait long for replies; if you need something from someone, request
  it in the app and carry on (note whether it arrived and how you'd know).
- Don't change or delete other people's records unless your role would
  (the lab manager may tidy shared stock). Don't touch account settings
  other than your own.

## Time

The app uses today's real date. Plan about **two weeks of work**, then
record it as "Day 1 … Day 10" (working days). Where the app lets you date
something (an entry date, a start date), use the simulated day; where it
doesn't, note it. Things that recur (passaging cells every 2–3 days, daily
checks) should be recorded each time they happen, as they would be: that is
how you find the tedium.

## Rules

- Privacy: everything will be published. Use only fictional names (the
  lab's five people: Morgan, Quinn, Avery, Rowan, Sasha). No real
  people, institutions, emails or hosts. Never read
  `repo/.private-words`.
- Don't contact anything outside this machine. Don't push, open issues or
  send email.
- Be honest: record what you actually did and saw. "I couldn't find how"
  is a valid, valuable result; say where you looked. A guessed "it works"
  is not.
- Keep evidence (your scripts, screenshots, page text) under
  `testing/wetlab/<your-name>/` (scripts/ and evidence/).
- Time budget: about 60–90 minutes of work.

## Your report

Write it with Bash (`cat > testing/wetlab/<your-name>/REPORT.md <<'EOF' … EOF`)
and also return it as your final message. Sections:

1. **Who I am and my project** (3–5 lines).
2. **My two-week plan**: what a real person in your role would do, before
   touching the app.
3. **Day-by-day log**: a table `| Day | What I did at the bench | How I
   recorded it in the app (where, steps/clicks) | Worked? | Friction |`.
4. **Requirements coverage**: a table of every need you had
   `| Need | Covered? (yes / partly / no) | Where in the app, or the
   workaround |`.
5. **Tedious, repeated work**: each with how often, steps each time, and
   what would remove it.
6. **Suggested new functions**, most valuable first: `| Function | The
   problem it solves (from this test) | What it would do | How often it
   would help | Effort guess (S/M/L) |`.
7. **Bugs or confusing things** you met (steps, what happened, expected).
8. **What worked well** (short, honest).
9. **Evidence**: where your scripts and screenshots are.

Final message: 5 lines summary, then the report.
