# App Studio decisions

The durable agreement between learner and AI. Update only agreed decisions and
actual evidence; pending is a valid state. Keep explanations/help in
[LEARNING.md](LEARNING.md), not a second copy here.

## Current stage

- **Current feature:** APP-001.
- **Status:** APP-001 built and kept by the learner; PR, CI and merge pending.
- **Next step:** Open the APP-001 PR, review CI, merge, then agree APP-002.
- **Implementation marker:** `studio.json` starts at `implemented_through: 0`.

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
| Own issue / branch / PR | [Issue #1](https://github.com/apink634/my-app-studio/issues/1); branch `app-001-homepage`; PR: Pending |

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
| Expected public/private behavior and account flow | Pending |
| Valid and rejected cases to demonstrate | Pending |
| Own issue / branch / PR | Pending |

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
| Intended admin-only result | Pending |
| Actual allowed/denied request evidence | Pending |
| Own issue / branch / PR | Pending |

**Keep when:** a direct request cannot bypass the role boundary, role changes
take effect as specified, new signup remains member-only, and full cumulative
checks plus AI review pass. Link the learner's actual interpretation/observation,
reviewed record and verified GitHub result. Hidden navigation alone is insufficient.

## Evidence

Link actual files/checks and the student's own issues/PRs. No fabricated URLs,
customer research or claims that a timestamp proves learning.

| Feature | Files / own issue / PR | Actual checks and learner observations | Kept / GitHub state |
|---|---|---|---|
| APP-001 | `app/brand.json`, `app/templates/home.html`, `app/static/logo.svg`, `app/static/site.css`, `app/static/art/cat.jpg`; [issue #1](https://github.com/apink634/my-app-studio/issues/1); PR: Pending | Local `check --lesson APP-001` on Windows: Black clean, Pylint clean, APP-001 contracts 2 passed, real Chromium journeys 2 passed, foundation 95 passed and 1 failed (`test_revision_does_not_read_symlinked_private_file`: WinError 1314, Windows needs a privilege to create symlinks). The failing test is outside the homepage. CI result: Pending. Learner observations: [LEARNING.md](LEARNING.md). | Pending |
| APP-002 | Pending | Unfinished; explicit contracts not yet passed | Pending |
| APP-003 | Pending | Unfinished; explicit contracts not yet passed | Pending |

The instructor's reference branches show possible implementations. They do not
establish this repository's completion or the learner's own reasoning.
