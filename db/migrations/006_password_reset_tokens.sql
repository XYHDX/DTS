-- Migration 006: Add password_reset_tokens table for secure time-limited reset flow
-- Replaces the plaintext temporary password approach (security fix for DAM-323)

CREATE TABLE IF NOT EXISTS password_reset_tokens (
    id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID        NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash  TEXT        NOT NULL,
    expires_at  TIMESTAMPTZ NOT NULL,
    used_at     TIMESTAMPTZ,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_prt_token_hash ON password_reset_tokens(token_hash);
CREATE INDEX IF NOT EXISTS idx_prt_user_id    ON password_reset_tokens(user_id);

COMMENT ON TABLE  password_reset_tokens              IS 'Time-limited, single-use tokens for the forgot-password flow.';
COMMENT ON COLUMN password_reset_tokens.token_hash   IS 'SHA-256 hex digest of the raw URL token. The raw token is never stored.';
COMMENT ON COLUMN password_reset_tokens.expires_at   IS 'Token is invalid after this timestamp (30 minutes from creation).';
COMMENT ON COLUMN password_reset_tokens.used_at      IS 'Set when the token is consumed. NULL means not yet used.';
