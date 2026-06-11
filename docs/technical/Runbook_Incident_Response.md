# Runbook — Incident response

> Followed when production is materially degraded for passengers or drivers. Target time to **first stabilising action: 10 minutes from page**. Postmortem within 5 working days.

## What counts as an incident

| Class | Examples | Page on-call? |
|---|---|---|
| **SEV-1** | API returning 5xx > 5% for 5 minutes, GPS stream silent for >15 minutes, login completely down | Yes, immediately |
| **SEV-2** | One route's data missing, push notifications not delivering, dashboard map blank | Yes, with a 30-minute SLA |
| **SEV-3** | Single endpoint slow, one driver report stuck, cosmetic regression | No, file a ticket |

If you're unsure, treat as one level higher.

## Roles during an incident

- **Incident Commander (IC).** Owns the response. Picks one teammate, communicates status, makes call/no-call decisions. Does **not** debug — they coordinate.
- **Operator.** Hands on keyboard. One person. Touches prod, runs queries, ships hotfixes.
- **Communicator.** Posts to the status page, internal Slack, and (for SEV-1) the public Twitter / WhatsApp channels.

In a small team one person fills more than one role; the IC role is non-negotiable and stays separate from Operator.

## Step 1 — Stabilise (target 0–10 min)

The first goal is to stop bleeding, not to understand. Pick the cheapest reversible action.

1. **Page** Sentry on-call alert (already wired). Acknowledge in the alert thread.
2. **Check `/api/health/deep`** on prod. Note which sub-check failed (DB / Redis / position-freshness).
3. **If DB is unreachable:** check Supabase status page. If Supabase shows green but we don't, we likely changed an env var. Roll back the last Vercel deployment (`vercel rollback`).
4. **If Redis is unreachable:** the rate limiter falls through to in-memory mode (ADR-003), so login still works. Note the degradation but do not roll back unless paired with another failure.
5. **If position-freshness fails during service hours:** the GPS ingest pipeline is broken. Check Traccar dashboard for connectivity to our `/api/traccar/position` endpoint. Replay the last known healthy webhook batch.
6. **If `vercel.com` itself is degraded:** flip DNS to the Docker compose fallback. See `DOCKER_MINISTRY_DEPLOY.md`.

## Step 2 — Communicate (always concurrent with Step 1)

The Communicator posts an update **every 30 minutes** during a SEV-1, every hour for SEV-2.

Template — initial post:

> ⚠ We are investigating reports of <symptom> since <time UTC>. Some drivers and passengers may see <impact>. We'll post the next update by <time + 30m>.

Template — resolved:

> ✓ The <symptom> issue is resolved as of <time UTC>. Trigger was <one-line>. A full postmortem will follow within five working days.

Internal Slack uses the same templates but adds the deploy or query that fixed it.

## Step 3 — Diagnose (after stabilise)

Only after the symptom is contained do you debug. Use:

```bash
# Recent error rate
curl -sS https://syrian-transit-system.vercel.app/api/health/deep | jq

# Last 100 5xx in Vercel logs
vercel logs --since=30m | grep -E '" 5[0-9]{2} '

# Sentry recent unhandled (replace URL)
open "https://sentry.io/issues/?project=…&statsPeriod=1h"

# Position-stream sanity
curl -sS https://syrian-transit-system.vercel.app/api/stream \
  -H 'Accept: text/event-stream' --max-time 10 | head -c 4000
```

Common signatures and probable causes:

| Symptom | Probable cause | First check |
|---|---|---|
| 5xx burst on `/api/auth/login` | Redis outage + rate limiter contention | Upstash status |
| `/api/health/deep` returns 503 but `/api/health` returns 200 | Position-freshness gate failed | Traccar pipeline |
| Map empty for everyone | SSE stream task crashed | `vercel logs` for `_ws_broadcast_loop` |
| Map empty for one user only | Their browser CSP / SSE policy | Inspect their network tab |
| Login works but admin actions 403 | M3 operator-scope mismatch | Check token claims |

## Step 4 — Stabilise the fix (after diagnose)

Two paths, in order of preference:

- **Rollback.** If the incident started during or right after a deploy, `vercel rollback` is the first thing to try. It's reversible in seconds.
- **Hotfix.** Follow `Runbook_Hotfix_Deploy.md`.

Do not try to push a creative fix in the heat of the moment. If the IC is uncertain, **roll back** and figure out the right fix tomorrow.

## Step 5 — Verify recovery

Run the same checks you used in Step 1, plus:

- [ ] `/api/health/deep` returns 200 with all three checks healthy.
- [ ] Sentry shows no new clusters in the last 15 minutes.
- [ ] At least one real user (driver or passenger) confirms in Slack that the app works for them.

## Step 6 — Postmortem (within 5 working days)

The postmortem document lives at `markdown-files/technical/Postmortem_YYYY-MM-DD.md`. Use this template:

```markdown
# Postmortem — <one-line title>

- **Severity:** SEV-N
- **Detected:** YYYY-MM-DD HH:MM UTC
- **Resolved:** YYYY-MM-DD HH:MM UTC
- **Duration:** N minutes
- **Authored:** <name>

## Impact
Who saw what, for how long. Be specific. "All passengers using the live map saw a blank screen for 14 minutes."

## Timeline
12:00 UTC — Sentry alert fires.
12:02 UTC — IC assigned, Operator begins log review.
…

## Root cause
One paragraph. Be honest. Avoid passive voice.

## What worked
Where the existing systems / runbooks / monitors caught us.

## What didn't
Where we wished we had more visibility, faster tools, clearer ownership.

## Action items
- [ ] Owner — small change to prevent recurrence
- [ ] Owner — observability improvement
- [ ] Owner — runbook update

## Lessons
Two or three sentences. No blame.
```

Postmortems are **blameless**. The point is to learn, not to assign fault. Action items are tracked in `ROADMAP_100.md` so they don't drop.

## Useful commands during an incident

```bash
# Block / unblock a single IP at the rate limiter (in-memory fallback only)
redis-cli SET "rl:blocked:<ip>" "1" EX 3600

# Drain a Vercel function
vercel rm --safe https://syrian-transit-system.vercel.app

# Read the last 50 incidents from the database
psql "$SUPABASE_DB_URL" \
  -c "SELECT id, kind, severity, created_at FROM alerts ORDER BY created_at DESC LIMIT 50;"

# Force-cycle a Supabase Realtime subscription (if push isn't delivering)
curl -X POST "$SUPABASE_URL/realtime/v1/api/broadcast" \
     -H "apikey: $SUPABASE_ANON_KEY" \
     -d '{"channel": "vehicles", "event": "cycle"}'
```
