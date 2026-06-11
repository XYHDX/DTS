# Runbook — Hotfix deploy to production

> When prod is broken and main has a fix that has not been tested through the normal cadence, follow this. Target time: **15 minutes from "we have a fix" to "fix is live."**

## Pre-flight (2 min)

- [ ] The fix exists as a commit on a branch off `main`. If only a local diff exists, push it first.
- [ ] You are logged into Vercel (`vercel whoami`), Supabase (web console), and Sentry.
- [ ] You have the prod `.env.production` values to hand — never paste them into chat.
- [ ] At least one teammate is in the loop on Slack or Discord. Hotfixes are not solo work.

## Decision (2 min)

Pick exactly one path:

| Situation | Path |
|---|---|
| Bug introduced in the last deploy | **Revert** (preferred) |
| Bug pre-existing, fix is one or two files | **Patch** (this runbook) |
| Bug is in the database tier | Stop. See `Runbook_DB_Backup_Restore.md`. |

If you chose revert, you do not need this runbook — run `vercel rollback` on the prior production deployment and skip to "Verify."

## Patch (5 min)

```bash
# 1. Bring the hotfix on top of current main.
git fetch origin main
git checkout -b hotfix/<short-name> origin/main
git cherry-pick <fix-commit>

# 2. Smoke test locally with prod-like env.
cp .env.production .env
pytest -q tests/test_security.py tests/test_auth_flow.py tests/test_happy_paths.py
# Use the targeted tests — full 307-test run takes ~15 min and is overkill here.

# 3. Push and watch CI.
git push origin hotfix/<short-name>
gh pr create --title "hotfix: <one-liner>" --body "Fixes <issue>." --base main
```

CI must go green on at least lint + test. Skipping CI for "speed" is not allowed — Vercel will not deploy if CI fails anyway.

## Deploy (3 min)

Two options. Pick one:

### A. PR merge → automatic Vercel deploy

```bash
gh pr merge --squash --auto
# Wait for GitHub Actions to flip green
# Wait for Vercel to flip green
```

### B. Direct production deploy (only if the merge queue is broken)

```bash
vercel --prod
# Confirm the URL is https://syrian-transit-system.vercel.app
```

## Verify (3 min)

Run all four checks. Do not declare done until every box is ticked.

- [ ] `curl -sS https://syrian-transit-system.vercel.app/api/health` returns `"status": "healthy"`.
- [ ] `curl -sS https://syrian-transit-system.vercel.app/api/health/deep` returns 200 and `position_fresh_6h: true`.
- [ ] The dashboard at `/` loads and shows live vehicle markers within 10 seconds.
- [ ] Sentry shows no new issue clusters in the 5 minutes since deploy.

## Post-incident (within 24 h)

- [ ] Open a bug-of-the-hotfix issue describing the original defect (so the fix has a paper trail beyond the commit).
- [ ] Write a 5-line incident note in `markdown-files/technical/Health_Log.md`: trigger, fix, deploy time, verified-by, follow-ups.
- [ ] If the underlying class of bug is preventable, open a follow-up ticket against `ROADMAP_100.md` (e.g. add a regression test, tighten CI, add a Playwright step).

## Backout plan

If the hotfix itself is bad:

```bash
vercel rollback                      # rolls to prior production deployment
# OR
git revert <hotfix-commit> --no-edit && git push origin main
```

The rollback path is faster (seconds) and should be the first choice during an active incident.
