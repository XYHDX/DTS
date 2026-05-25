-- Migration 007 — password_changed_at
-- Adds a column tracking the most recent password change so JWTs issued before
-- that timestamp can be invalidated by api.core.auth.is_token_revoked_by_password_change.
-- Pairs with the `iat` claim added to JWTs in auth.py.

BEGIN;

ALTER TABLE users
    ADD COLUMN IF NOT EXISTS password_changed_at TIMESTAMPTZ NOT NULL DEFAULT NOW();

-- Triggered on password updates only — keep existing rows untouched on backfill.
CREATE OR REPLACE FUNCTION users_touch_password_changed_at()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.password_hash IS DISTINCT FROM OLD.password_hash THEN
        NEW.password_changed_at := NOW();
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS users_password_changed_at_trg ON users;
CREATE TRIGGER users_password_changed_at_trg
    BEFORE UPDATE ON users
    FOR EACH ROW
    EXECUTE FUNCTION users_touch_password_changed_at();

COMMENT ON COLUMN users.password_changed_at IS
    'Updated automatically when password_hash changes. Used to revoke JWTs with iat < this timestamp.';

COMMIT;
