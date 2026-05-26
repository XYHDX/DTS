# Runbook — Rotate `JWT_SECRET` without taking the API down

> Rotating `JWT_SECRET` invalidates every issued JWT instantly. Done naively that signs out every driver mid-shift. This runbook describes how to do it without service interruption.

## When to rotate

- The current secret was committed by mistake (git history, public Slack, screenshot).
- A teammate with prod access left the team.
- Quarterly hygiene rotation.
- Sentry/Cloudflare/Upstash leak that *might* have included the env var.

If you have any real suspicion of leak, rotate immediately — there is no "wait for a maintenance window" answer.

## Strategy

The API supports an **overlap window** of two secrets via the `JWT_SECRET_PREVIOUS` env var. During the rotation window, both old and new tokens validate. After the longest valid JWT lifetime (24 h) has elapsed, the old secret is removed.

If the codebase does not yet implement `JWT_SECRET_PREVIOUS` (it currently does not — this runbook documents the intended state), patch `api/core/auth.py` to try the previous secret on `InvalidSignatureError` before merging this runbook into prod practice. The TTL-cached revocation logic from step 14 stays unchanged.

## Procedure

### 0. Prepare new secret

```bash
# 64 random URL-safe characters
python3 -c "import secrets; print(secrets.token_urlsafe(48))"
```

Store in 1Password / Hashicorp Vault. Do **not** put it in chat, in a commit, or in a screenshot.

### 1. Stage the new secret (no rollover yet)

In the Vercel dashboard (Project → Settings → Environment Variables → Production):

```
JWT_SECRET_PREVIOUS = <CURRENT VALUE>      (new env var)
JWT_SECRET          = <NEW VALUE>          (replace the existing value)
```

Trigger a redeploy via `vercel --prod` or by pushing a no-op commit to `main`.

### 2. Verify both secrets validate

```bash
# Old token issued before the rotation — must still work
TOKEN_OLD=$(jq -r .token .testdata/pre-rotation-login.json)
curl -sS -H "Authorization: Bearer $TOKEN_OLD" \
     https://syrian-transit-system.vercel.app/api/admin/users \
  | head -c 200

# Fresh login — uses the new secret
curl -sS -X POST -H 'Content-Type: application/json' \
     -d '{"email":"ops@damascustransit.sy","password":"…"}' \
     https://syrian-transit-system.vercel.app/api/auth/login
```

Both should return 200. If the old token comes back 401, the deploy did not pick up `JWT_SECRET_PREVIOUS` — fix that before continuing.

### 3. Wait out the overlap window

Tokens are valid for 24 h (`JWT_EXPIRATION_HOURS` in `api/core/auth.py`). Wait at least 25 hours from the redeploy timestamp before removing the previous secret. Mark the calendar.

If the rotation is in response to a confirmed leak, **skip the wait** — accept that drivers will need to log in again. Notify them via push or SMS first.

### 4. Drop the previous secret

In the Vercel dashboard, delete `JWT_SECRET_PREVIOUS`. Redeploy. From now on only the new secret validates.

### 5. Verify

```bash
curl -sS -H "Authorization: Bearer $TOKEN_OLD" \
     https://syrian-transit-system.vercel.app/api/admin/users
# Expected: HTTP 401, body {"detail":"Invalid token"}
```

Old tokens are now refused. Rotation complete.

## What if a driver complains mid-rotation?

```bash
# Force-logout one user (M1 path — bumps password_changed_at then drops cached entry).
psql "$SUPABASE_DB_URL" -c "UPDATE users SET password_changed_at = NOW() WHERE email = 'driver@example.com';"
```

Any token issued before this moment is revoked. The user is told to log in again.

## Backout plan

If you rotated and the new secret turns out to be malformed (too short, wrong escape, etc.):

1. In Vercel, swap `JWT_SECRET` back to the value still stored in `JWT_SECRET_PREVIOUS`.
2. Redeploy.
3. Everyone who logged in during the rotation window has a token signed by the bad secret — they will need to log in again. Communicate this.

## Logging

After completion, append to `markdown-files/technical/Health_Log.md`:

```
## YYYY-MM-DD HH:MM UTC — JWT_SECRET rotated
- Rotation reason: <hygiene | leak | offboarding>
- Overlap window: <start> → <end>
- Rotated by: <name>
- Verified by: <name>
- Backout used: no
```
