# Git Workflow

## Repository

BasketGuard uses this GitHub repository:

```text
https://github.com/TimBow88/BasketGuard.git
```

Local remote name:

```text
origin
```

Default branch:

```text
main
```

## Local Setup

From the project root:

```powershell
git remote -v
git status
```

Expected remote:

```text
origin  https://github.com/TimBow88/BasketGuard.git (fetch)
origin  https://github.com/TimBow88/BasketGuard.git (push)
```

If Git identity is not configured, set it before committing:

```powershell
git config user.name "Your Name"
git config user.email "you@example.com"
```

Use local config for this project unless a global identity is already correct.

## Branching Rules

Use `main` as the stable branch.

Do not commit directly to `main` after the initial project import unless the change is trivial documentation-only work.

Use short feature branches:

```text
feature/grouping-rules
feature/tesco-parser
feature/report-generator
fix/unit-normalisation
docs/git-workflow
```

Branch naming:

| Prefix | Use |
|---|---|
| `feature/` | New capability |
| `fix/` | Bug fix |
| `docs/` | Documentation-only change |
| `test/` | Test-only or fixture-focused change |
| `chore/` | Tooling, cleanup, repo maintenance |

## Standard Change Procedure

1. Check current state:

```powershell
git status
git branch --show-current
```

2. Create a branch:

```powershell
git switch -c feature/tesco-parser
```

3. Make the smallest coherent change.

4. Run tests:

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'; python -m unittest discover -s tests -v
```

5. Review changed files:

```powershell
git status --short
git diff
```

6. Stage intentionally:

```powershell
git add path/to/file.py path/to/test.py
```

Avoid broad staging with `git add .` unless the diff has already been reviewed.

7. Commit:

```powershell
git commit -m "Add Tesco product page parser"
```

8. Push branch:

```powershell
git push -u origin feature/tesco-parser
```

9. Open a pull request on GitHub.

## Commit Message Style

Use imperative, specific commit messages.

Good:

```text
Add Tesco product page parser
Add cornflakes grouping fixtures
Fix pints to litre conversion
Document grouping confidence policy
```

Avoid:

```text
updates
changes
work in progress
fix stuff
```

## Pull Request Requirements

Each PR should include:

1. summary of what changed;
2. tests run;
3. known limitations;
4. screenshots if UI changed;
5. migration notes if database changed.

Example:

```text
Summary
- Adds Tesco saved-HTML parser.
- Adds disabled-by-default allowlisted provider.
- Adds parser fixtures for shelf price and Clubcard price.

Tests
- python -m unittest discover -s tests -v

Notes
- No live Tesco requests are made unless the feature flag is set.
```

## Testing Policy

Run the full suite before every commit:

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'; python -m unittest discover -s tests -v
```

Current suite covers:

1. analytics;
2. product normalisation;
3. ingestion contracts and allowlisted collection targets;
4. Tesco and Asda parsers/providers;
5. fetcher abstraction;
6. snapshot artifact store;
7. database row mapping and repository persistence;
8. ingestion pipeline, local persistence command and supplier batch workflow;
9. reporting;
10. seed fixtures;
11. static UI asset checks;
12. gated live PostgreSQL integration (skipped unless `BASKETGUARD_RUN_POSTGRES_INTEGRATION=1`).

## Database Migration Policy

Database changes must be added as numbered SQL migrations in:

```text
db/migrations/
```

Rules:

1. never edit an applied migration after it has been pushed;
2. add a new numbered migration instead;
3. keep migrations deterministic;
4. include indexes and constraints with the table where practical;
5. update `db/README.md` when adding migration scope.

## Scraper Safety Policy

Live scraping must remain disabled by default.

For Tesco, live collection requires both:

```text
TescoScraperConfig.enabled = true
BASKETGUARD_ENABLE_TESCO_SCRAPER = 1
```

For Asda, live collection requires both:

```text
AsdaScraperConfig.enabled = true
BASKETGUARD_ENABLE_ASDA_SCRAPER = 1
```

For Sainsbury's, live collection requires both:

```text
SainsburysScraperConfig.enabled = true
BASKETGUARD_ENABLE_SAINSBURYS_SCRAPER = 1
```

Any new retailer must follow the same pattern: a provider config flag plus a
`BASKETGUARD_ENABLE_<RETAILER>_SCRAPER` environment flag, with fixture-backed
parser tests before live collection is enabled. Unsupported retailers in seed
files are staged as skipped attempts, never fetched.

Rules:

1. use explicit allowlisted product URLs only;
2. do not crawl category pages broadly;
3. keep request rates conservative;
4. save raw snapshots before parsing;
5. test parser behaviour with saved HTML fixtures first;
6. record parser errors, missing price count and block indicators.

## Release Tags

GitHub manages change control through branches, pull requests, CI evidence,
merge history and tags. Linear remains the single source of truth for planned
work and live issue status.

Use lightweight milestone tags only for accepted delivery history until the
product has deployable packages:

```powershell
git tag milestone-00X-short-name <commit>
git push origin --tags
```

Only tag after tests pass.

Do not maintain a duplicate tag list in this file. Inspect tags with
`git tag --list "milestone-*"` and use
[docs/11_CODEX_WORKPLAN.md](11_CODEX_WORKPLAN.md) only as a readable historical
ledger of delivered milestones.

## Progress Tracking Procedure

Use Linear as the authoritative progress ledger for active and planned work.
Use GitHub as the accepted-change ledger. A delivered milestone, when used,
needs both:

1. a row in the "Delivered Milestones" table;
2. a matching lightweight git tag.

The supporting checklist in
[docs/backend/10_IMPLEMENTATION_CHECKLIST.md](backend/10_IMPLEMENTATION_CHECKLIST.md)
tracks durable capability detail. The roadmap in
[docs/backend/08_MVP_DELIVERY_ROADMAP.md](backend/08_MVP_DELIVERY_ROADMAP.md)
tracks historical direction and phase framing, not the active queue.

Before reporting progress, check:

```powershell
git tag --list "milestone-*"
python -m unittest discover -s tests -v
```

Also check the BasketGuard project in Linear for issue status, priority and
sequencing.

If a capability exists in code but has no milestone tag, describe it as
implemented but not milestone-recorded. If a roadmap prompt says something is
next but Linear or GitHub shows otherwise, treat the prompt as historical and
update it through a documentation change.

## Recovery Commands

Inspect changes:

```powershell
git status --short
git diff
```

Unstage a file:

```powershell
git restore --staged path/to/file
```

Discard changes to a file only when you are certain they are not needed:

```powershell
git restore path/to/file
```

Do not use destructive commands such as:

```powershell
git reset --hard
```

unless the exact consequence is understood and explicitly approved.

## Initial Import Status

The initial import is complete: `main` (commit `aac9eff`, "Initial BasketGuard prototype") is pushed to `origin` and verified on GitHub.

All work after that commit must follow the branching rules above: create a short feature branch, run the full test suite, and merge to `main` through a pull request. Substantial local work accumulated directly on `main` should be moved to a feature branch before committing.
