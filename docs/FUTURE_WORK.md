# Future work — deferred, intentionally not done yet

Living backlog of things we consciously postponed. Each entry says *why* it's
deferred and what would trigger doing it, so nothing is silently forgotten.

## Migration runner / schema-drift control — DEFERRED (owner's call, 2026-06-25)
**What:** A CI/deploy step that applies `db/migrations/*.sql` in order before
code deploys, plus a startup assertion that confirms which migrations are live.
A scaffold already exists at `.github/workflows/migrate.yml` (inert until the
`SUPABASE_DB_URL` secret is added).

**Why deferred:** Touches the live production database and needs hosting
secrets; out of scope for the current "fix the code-level errors" pass.

**Why it still matters:** Schema drift between the repo and prod is the root
cause behind past outages and a previously-hidden ingest bug. Until a runner
exists, migrations are hand-applied and can be missed.

**Trigger to pick up:** before the next schema-dependent feature ships, or as
soon as a second environment (staging) is introduced.

**Related follow-up — make the approval gate strictly fail-closed:** the gate
is now fail-closed *when the `approval_status` column is present* (it probes at
runtime and only relaxes if the column is genuinely absent — see
`api/core/approval.py`). Once a migration runner guarantees migration 019 is
applied everywhere, the runtime tolerance can be dropped entirely for a hard,
unconditional fail-closed.

## Backup PII exposure — STILL OPEN (not selected for the 2026-06-25 pass)
`.github/workflows/backup.yml` publishes an **unencrypted** monthly DB dump
(includes the `users` table: password hashes, emails, phones) to a GitHub
Release. On a public repo these assets are world-readable. Fix when ready:
encrypt before upload (age/gpg with a CI secret) and/or stop attaching dumps to
Releases, and make the repo private. Tracked so it isn't lost.

## Other deferred items (from the audits / efficient roadmap)
- **SHA-pin GitHub Actions** + pin the Docker base image to a digest (supply chain).
- **Cross-tenant isolation tests** + `FORCE ROW LEVEL SECURITY` before a 2nd operator.
- **Scale infra (Kafka, broker, cold-path partitioning)** — gated behind the
  measured triggers in `docs/adr/ADR-005-capacity-and-cost.md`; do not build early.
