# BioManager 1.0 pre-release test: security

54 tests: 37 PASS, 2 FAIL, 15 WARN. Evidence and re-runnable scripts: `evidence/`.

## 1. Scope and environment
- Code: master `76371cf` (v0.10.2 + icon), unmodified.
- Server: `gunicorn -c gunicorn.conf.py wsgi:app` (production mode) on 127.0.0.1:5103, 1 worker × 4 threads; `BIOMANAGER_HTTPS=0`, CSP enforced. Extra runs: CSP off; `HTTPS=1 PROXY_HOPS=1`; an empty data folder (setup code).
- Database: SQLite (access-control tests).
- Data: demo lab "Rivera Lab" (`scripts/demo-data.py`): alex (admin), sam, jordan, priya (members); 39 mice, 14 cages, 8 plasmids, 2 stock and 5 inventory databases; plus a personal inventory, uploads, planted payloads, 2 guest passes, 60+ pending sign-ups.
- Clients: Python `requests` signing in through `/login`; Playwright Chromium 141. Cross-site tests used `http://labserver.test:5103` and `http://evil.test/` via host-resolver rules (nothing left the machine).
- Surface: 390 URL rules (`evidence/routes.json`).

## 2. Test log
| ID | What | How | Expected | Result | Evidence |
|---|---|---|---|---|---|
| SEC-01 | Every route signed out | anon_probe.py: 390 rules, GET+POST, 408 requests | Redirect or 401/403/404/405 except public pages | PASS: only /, /login, /register, /guest, /healthz, /csp-report, /guide answered (+ /milestone/x, a no-op 204) | anon_probe.txt/.json |
| SEC-02 | Signed-out front page | GET / | Lab name and database names by design | PASS (by design, no records) | anon_probe.txt |
| SEC-03 | Admin pages as a member | role_diff.py: 134 GET routes, alex vs sam | Refused | PASS | role_diff.txt |
| SEC-04 | Admin actions as a member | 20 POSTs (self-promote, demote, disable, reset password, Lab setup, guests, printer, racks, built-ins, feedback, delete/configure lab databases); 7 tables hashed before/after | Refused, nothing changes | PASS | member_admin_posts.txt |
| SEC-05 | Notebook privacy, no share | jordan and alex against sam's page, 11 GET + 19 POST | 404, nothing changes | PASS (404 even for the admin) | notebook_acl.txt |
| SEC-06 | Notebook view share | priya with a view share | Read and comment only | PASS (edit/share/restore/sign/compact/delete 403) | notebook_acl.txt |
| SEC-07 | Personal database | jordan tries 21 ways into sam's personal inventory | Nothing | PASS | personal_db.txt |
| SEC-08 | Edit rights per record | jordan vs sam's mouse, private cage, plasmid; pages and API | Refused | PASS | record_perms.txt |
| SEC-09 | Cross-site forgery in a browser | plain-HTTP LAN name; auto-post, no-referrer, no-cors fetch, sign-out, login CSRF | Refused | PASS (every POST 403, data unchanged) | csrf_browser.txt, csrf-*.png |
| SEC-10 | Cross-site rule by header | 11 combinations | As designed | PASS | csrf_headers.txt |
| SEC-11 | Framing | iframe from evil.test | Blocked | PASS | csrf-iframe_frame.png |
| SEC-12 | Stored script injection, CSP on | 17 fields (incl. Markdown script/onerror/javascript:), 27 pages × 2 users | Nothing runs | PASS (0 executions, 0 CSP violations) | xss_crawl_csp-enforce.* |
| SEC-13 | Same, CSP off | BIOMANAGER_CSP=off | Escaping holds | PASS (0 on 54 loads) | xss_crawl_csp-off.* |
| SEC-14 | JavaScript-drawn parts | Ctrl+K palette, notebook links | Text only | PASS | xss_widgets_csp-off.txt |
| SEC-15 | Raw responses | 143 URLs | No unescaped payload in HTML | PASS | xss_raw_scan.txt |
| SEC-16 | Upload serving | html, svg, HTML named .png, pdf, traversal name | Sign-in required; HTML/SVG downloaded, sandboxed | PASS | uploads.txt |
| SEC-17 | Traversal in upload URLs | 7 variants incl. --path-as-is | 404 | PASS | uploads.txt |
| SEC-18 | Upload size | 65 MB | 413 | PASS | uploads.txt |
| SEC-19 | Who can open an upload | jordan or a guest opens sam's private-page attachment | Stays with the page | WARN: any signed-in account with the URL (64-bit random names) | uploads.txt |
| SEC-20 | Cookie flags | Set-Cookie on sign-in | HttpOnly, Lax, 7 days | PASS | sessions.txt |
| SEC-21 | HTTPS mode behind a proxy | https_proxy.py | Secure cookie, plain-HTTP sign-in refused, HSTS | PASS | https_proxy.txt |
| SEC-22 | Sign-out ends the session | Replay cookie after Sign out | Refused | WARN: still signed in | sessions.txt |
| SEC-23 | Password change | Two browsers | Other signed out | PASS | sessions.txt |
| SEC-24 | Disable then enable | Session across the change | Stays out | WARN: old cookie works again | sessions.txt |
| SEC-25 | Role change applies at once | Promote/demote | Immediate | PASS | sessions.txt |
| SEC-26 | Altered or forged cookie | Byte changed; dev key | Refused | PASS | sessions.txt |
| SEC-27 | Sign-in throttle, account discovery | throttle.py | Same message/timing; 429 after 10 | PASS (107 vs 110 ms) | throttle.txt |
| SEC-28 | Lock-out as a weapon | Same run | — | WARN: anyone locks a username (admin too) for 15 min | throttle.txt |
| SEC-29 | Spoofed X-Forwarded-For | PROXY_HOPS=1, direct | Per-user limit holds | PASS | https_proxy.txt |
| SEC-30 | Open redirect | 14 next= values, Referer tricks | Same site | PASS | open_redirect.txt |
| SEC-31 | First-account setup code | Empty folder | Only the right code; file then deleted | PASS (0600, never on a page) | setup_code.txt |
| SEC-32 | Sign-up flood | 60 sign-ups | Some limit | WARN: 60 in 9.1 s, 60 admin notifications | register_spam.txt |
| SEC-33 | Look-alike usernames | Alex, ALEX, Cyrillic, `*` | Refused | WARN: all accepted as pending | register_spam.txt |
| SEC-34 | Admin's copy of the lab | lab_copy.py snapshot (1,265,664 bytes) | Lab records | WARN: also every password hash and private notebook pages | lab_copy.txt |
| SEC-35 | Member's copy of the lab | Permission on, sam's key | Only what sam may see | **FAIL**: admin's hash, others' unshared pages, audit log, feedback | lab_copy_member.txt |
| SEC-36 | Guest pass and internet entrance | guests.py, X-BioManager-Entry: internet | Strangers see only the code page | PASS | guests.txt |
| SEC-37 | Guest takes a copy of the lab | Permission on | Refused | **FAIL**: whole database incl. password hashes | guests.txt |
| SEC-38 | Wrong lab-copy keys | lab_copy_throttle.py | Only the stranger throttled | WARN: valid key 429 after 20 anonymous wrong keys | lab_copy_throttle.txt |
| SEC-39 | Wrong guest codes | guest_throttle.py | — | WARN (documented): real guest 429 after 30 wrong codes | guest_throttle.txt |
| SEC-40 | SQL injection | 1,625 requests, 52 parameters × 13 payloads | None | PASS | injection_fuzz.txt |
| SEC-41 | Bad numbers in parameters | Same run | 400 or ignored | WARN: 14 × 500 (limit=x; 21-digit numbers in search, notebook page, stocks horizon) | injection_fuzz.txt |
| SEC-42 | Error pages | error_pages.py | No traceback | PASS | error_pages.txt |
| SEC-43 | Security headers | misc.py | nosniff, framing, referrer, CSP | PASS | misc.txt |
| SEC-44 | Back after Sign out | back_after_logout.py | No cached page | PASS | back_after_logout.* |
| SEC-45 | Formula injection | formula_injection.py | Written as text | WARN: live =HYPERLINK/+/@ in mouse CSV | formula_injection.txt |
| SEC-46 | Secrets in change history | 205 audit rows | None | PASS ([redacted]) | audit_redaction.txt |
| SEC-47 | API tokens | scope, cookie-only, ?access_token, CORS, revoke, disabled owner | Enforced | PASS | api_tokens.txt |
| SEC-48 | API replies set no cookie | Token + cookie | No Set-Cookie (per docs) | WARN: re-set | api_tokens.txt |
| SEC-49 | Current password in Settings | 30 guesses | Throttled | WARN: none refused | misc.txt |
| SEC-50 | /csp-report | Newline; 200 × 8 KB | Logged safely | WARN: forged log line, no limit | misc.txt |
| SEC-51 | Data folder permissions | stat, umask 022 | Secrets owner-only | WARN: db and uploads 0644 outside Docker | file_perms.txt |
| SEC-52 | XML bomb, XXE | xml_bomb.py | Refused | PASS | xml_bomb.txt |
| SEC-53 | Project security tests | 4 test modules | Pass | PASS (103 OK) | unit_tests.txt |
| SEC-54 | Google/Microsoft sign-in linking | Code review | By subject, never email | PASS (review only) | app/oidc.py |

## 3. Findings
- **F-1 (high; critical with the setting on)** Guest pass can download the whole database (SEC-37). `app/lab_copy.py:71` `may_keep_copies()` lacks the guest/pending/disabled checks that `app/api.py:70` has.
- **F-2 (high)** A member's copy holds everyone's private data and password hashes; the admin's copy holds private notebook pages (SEC-35, SEC-34). `app/lab_copy.py:186` `write_snapshot()` copies every table.
- **F-3 (medium)** Sign out does not end the session; a copied cookie works 7 idle days (`app/app.py:2146`, `security.session_stamp` tied to the password only).
- **F-4 (medium)** Formula injection in `/colony/mice/export` (`app/app.py:3197`).
- **F-5 (medium)** 20 anonymous wrong lab-copy keys lock out every laptop for 15 min (global throttle key, `app/lab_copy.py:145`).
- **F-6 (low)** Re-enabling an account revives old sessions.
- **F-7 (low)** No rate limit on /register.
- **F-8 (low)** Look-alike usernames accepted.
- **F-9 (low)** Anyone can lock a username with 10 wrong passwords.
- **F-10 (low)** 30 wrong guest codes lock every guest (documented choice).
- **F-11 (low)** 500s on non-numeric/huge numeric parameters (`limit`, search, notebook page, stocks horizon).
- **F-12 (low)** /csp-report writes forged log lines, no limit.
- **F-13 (low)** Settings current-password check not throttled.
- **F-14 (low)** db and uploads 0644 outside Docker.
- **F-15 (low)** Uploads readable by any signed-in account with the URL.
- **F-16 (low)** `api._no_cookie` runs before the session is saved, so Set-Cookie is still sent.

## 4. Numbers
URL rules 390; anonymous requests 408 (0 unexpected); member-vs-admin GET routes 134; admin POSTs as member 20 (0 took effect); injection page loads 108 (0 executions); raw URLs 143; SQL fuzz 1,625 requests (0 injections, 14 × 500); sign-in timing 107/110 ms; upload limit 64 MB; security unit tests 103 OK.
