-- ============================================================
-- Migration 017: Operational hardening (Phase 6.3)
-- ============================================================
-- Adds:
--   • revoked_tokens — JWT revocation list keyed by jti, used for the
--     admin "force logout this session" action.
--   • login_attempts — append-only log of every login attempt (success
--     OR failure) for brute-force detection and forensic review.
--   • A helper RPC failed_login_count() the API can ask "has this
--     email failed N times in the last M minutes?".
-- ============================================================

BEGIN;

-- 1. Revoked-tokens table.
-- jti is generated in _issue_jwt(); inserting a row here is enough to
-- kill the session. expires_at lets us prune rows once the JWT itself
-- has aged out (24h after issue). The unique index is the lookup.
CREATE TABLE IF NOT EXISTS revoked_tokens (
    jti          TEXT PRIMARY KEY,
    user_id      UUID REFERENCES users(id) ON DELETE CASCADE,
    revoked_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at   TIMESTAMPTZ NOT NULL,
    reason       TEXT
);
CREATE INDEX IF NOT EXISTS idx_revoked_tokens_user ON revoked_tokens(user_id);
CREATE INDEX IF NOT EXISTS idx_revoked_tokens_expiry ON revoked_tokens(expires_at);

ALTER TABLE revoked_tokens ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS admin_read_revoked ON revoked_tokens;
DROP POLICY IF EXISTS admin_write_revoked ON revoked_tokens;
CREATE POLICY admin_read_revoked ON revoked_tokens FOR SELECT
    USING (auth.jwt() ->> 'role' IN ('admin','super_admin'));
CREATE POLICY admin_write_revoked ON revoked_tokens FOR ALL
    USING (auth.jwt() ->> 'role' IN ('admin','super_admin'));

-- 2. Login attempts (brute-force detection + audit forensics).
CREATE TABLE IF NOT EXISTS login_attempts (
    id           BIGSERIAL PRIMARY KEY,
    email        TEXT NOT NULL,
    success      BOOLEAN NOT NULL,
    ip_address   TEXT,
    user_agent   TEXT,
    reason       TEXT,           -- e.g. 'invalid_password', 'account_locked'
    attempted_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_login_attempts_email_time
    ON login_attempts(email, attempted_at DESC);
CREATE INDEX IF NOT EXISTS idx_login_attempts_ip_time
    ON login_attempts(ip_address, attempted_at DESC);

ALTER TABLE login_attempts ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS admin_read_login_attempts ON login_attempts;
CREATE POLICY admin_read_login_attempts ON login_attempts FOR SELECT
    USING (auth.jwt() ->> 'role' IN ('admin','super_admin'));

-- 3. Lock-status column on users (used by the lockout flow).
ALTER TABLE users ADD COLUMN IF NOT EXISTS locked_until TIMESTAMPTZ;
COMMENT ON COLUMN users.locked_until IS
    'Set by the API when too many login failures stack up. While now() < '
    'locked_until, the login endpoint refuses to even attempt bcrypt for '
    'that email. Cleared on a successful password change.';

-- 4. RPC: how many failures in the last p_minutes for this email?
CREATE OR REPLACE FUNCTION failed_login_count(
    p_email   TEXT,
    p_minutes INTEGER DEFAULT 60
) RETURNS INTEGER AS $$
DECLARE
    n INTEGER;
BEGIN
    SELECT count(*) INTO n
      FROM login_attempts
     WHERE lower(email) = lower(p_email)
       AND success = false
       AND attempted_at >= NOW() - (p_minutes || ' minutes')::interval;
    RETURN COALESCE(n, 0);
END;
$$ LANGUAGE plpgsql STABLE;

COMMIT;
