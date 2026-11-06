# App Studio decisions

The durable agreement between learner and AI. Update only agreed decisions and
actual evidence; pending is a valid state. Keep explanations/help in
[LEARNING.md](LEARNING.md), not a second copy here.

## Current stage

- **Current feature:** APP-003.
- **Status:** APP-001 and APP-002 merged. APP-003 built, checked locally and kept by the learner; see PR #7 for CI and merge state.
- **Next step:** Verify CI and merge on PR #7, then submit.
- **Implementation marker:** `studio.json` is at `implemented_through: 3`.

This repository owns application code. Server/proxy changes and production
deployment are outside these three local-development lessons. Prepared helpers
are reusable foundations, not evidence that unfinished routes are implemented.

## APP-001 · Branded homepage

**Scope:** make the neutral FastAPI homepage express one chosen identity with
a simple original SVG mark, coherent copy, navigation and shared style tokens.
Keep account actions honest about their unfinished state.

| Decision | Agreement |
|---|---|
| Visitor and concrete use situation | A bored student in class looking for something to do. |
| Reused IS117 brand, or name / promise / primary archetype | IS117 brand not reused (it was a resume site). Name: MiniGallery. Promise: "Something more interesting to look at instead of zoning out in class." Primary archetype: Explorer, with some Jester in the voice. |
| One visible choice and visitor benefit | The page leads with the learner's own photo (`app/static/art/cat.jpg`) and a clickable "What am I looking at?" caption. Intended benefit: something more interesting to look at than zoning out. |
| Own issue / branch / PR | [Issue #1](https://github.com/apink634/my-app-studio/issues/1); branch `app-001-homepage`; [PR #2](https://github.com/apink634/my-app-studio/pull/2) |

**Not in scope (parked idea):** an archive of past pieces. It is a new feature, so it waits for a later agreed scope.

**Keep when:** the agreed identity is visible and usable at desktop/narrow widths;
full foundation + APP-001 checks pass; AI review and the learner's actual check
interpretation/browser observation/keep reason are recorded; reviewed evidence
and verified GitHub state are linked below.

## APP-002 · Signup, login and logout

**Scope:** add browser forms and REST behavior for member signup, login, a private
dashboard and logout backed by SQLite. Reuse the prepared password/JWT/CSRF/session
helpers; keep data local. New accounts cannot choose their role.

| Decision | Agreement |
|---|---|
| Expected public/private behavior and account flow | Anonymous visitors cannot see the private dashboard; the server sends them to the login page. A visitor makes an account, logs in, and lands on a private member space that welcomes them by username and shows a members-only note. Logging out ends the session and returns to the homepage. |
| Valid and rejected cases to demonstrate | Valid: signup with a username and a long-enough password, then login. Rejected: a password that is too short (seen in the browser); duplicate or invalid signup and wrong credentials are covered by the automated checks. |
| Own issue / branch / PR | [Issue #3](https://github.com/apink634/my-app-studio/issues/3); branch `app-002-accounts`; [PR #4](https://github.com/apink634/my-app-studio/pull/4) |

**Not in scope (parked ideas):** saved pieces on the dashboard, and the archive of past pieces. Both are new features for a later agreed scope.

**Keep when:** the agreed forms/API work; duplicate/invalid signup and wrong
credentials are rejected; passwords are hashed; authentication uses validated,
expiring JWTs with protected cookies and CSRF; private requests require a live
session and logout revokes it. Full cumulative checks, AI review, actual learner
contributions and GitHub state are recorded. This is not a production-security certification.

## APP-003 · Server-enforced roles

**Scope:** enforce a small member/admin boundary in the API and browser. Assign
roles only through the trusted local terminal command; use current server-side
permissions, including for an existing session after a role change.

| Visitor | Homepage | Member area | Admin area/API |
|---|---|---|---|
| Anonymous | Allowed | Login required | Login required |
| Member | Allowed | Allowed | Forbidden |
| Admin | Allowed | Allowed | Allowed |

| Decision | Agreement |
|---|---|
| Intended admin-only result | An admin sees an "Administration" page that says "Only the curator of the gallery can see this page." Members get "Admin access required" (403) and anonymous visitors are sent to the login page. |
| Actual allowed/denied request evidence | Direct `/api/admin` request: anonymous 401, member 403, admin 200 (automated checks). In my browser: as a member `/admin` said "Admin access required"; after the trusted terminal command made me an admin, a refresh showed "Administration". |
| Own issue / branch / PR | [Issue #6](https://github.com/apink634/my-app-studio/issues/6); branch `app-003-roles`; [PR #7](https://github.com/apink634/my-app-studio/pull/7) |

**Not in scope (parked idea):** admin tools for adding the new daily gallery photo. It is a new feature, so it waits for a later agreed scope.

**Keep when:** a direct request cannot bypass the role boundary, role changes
take effect as specified, new signup remains member-only, and full cumulative
checks plus AI review pass. Link the learner's actual interpretation/observation,
reviewed record and verified GitHub result. Hidden navigation alone is insufficient.

## Evidence

Link actual files/checks and the student's own issues/PRs. No fabricated URLs,
customer research or claims that a timestamp proves learning.

| Feature | Files / own issue / PR | Actual checks and learner observations | Kept / GitHub state |
|---|---|---|---|
| APP-001 | `app/brand.json`, `app/templates/home.html`, `app/static/logo.svg`, `app/static/site.css`, `app/static/art/cat.jpg`; [issue #1](https://github.com/apink634/my-app-studio/issues/1); [PR #2](https://github.com/apink634/my-app-studio/pull/2) | Local `check --lesson APP-001` on Windows first failed one foundation test (`test_revision_does_not_read_symlinked_private_file`, WinError 1314: Windows needs a privilege to create symlinks). After Windows Developer Mode was turned on, the full check passed, including real Chromium. CI: green. Learner observations: [LEARNING.md](LEARNING.md). | Kept; PR #2 merged, CI green |
| APP-002 | `app/features/accounts.py`, `app/templates/signup.html`, `login.html`, `dashboard.html`, `app/static/site.css`, `studio.json`; [issue #3](https://github.com/apink634/my-app-studio/issues/3); [PR #4](https://github.com/apink634/my-app-studio/pull/4) | Local `check --lesson APP-002` on Windows passed in full, including real Chromium, and was re-run after the dashboard revision. Learner observations: [LEARNING.md](LEARNING.md). | Kept; PR #4 merged, CI green |
| APP-003 | `app/features/roles.py`, `app/templates/admin.html`, `studio.json`; [issue #6](https://github.com/apink634/my-app-studio/issues/6); [PR #7](https://github.com/apink634/my-app-studio/pull/7) | Local `check --lesson APP-003` on Windows passed in full, including real Chromium (96 foundation, 18 contracts, 2 Chromium). Learner observations: [LEARNING.md](LEARNING.md). | Kept by the learner; CI and merge state are on PR #7 |

The instructor's reference branches show possible implementations. They do not
establish this repository's completion or the learner's own reasoning.
