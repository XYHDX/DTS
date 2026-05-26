-- Migration 005: Add must_change_password flag to users table
ALTER TABLE users ADD COLUMN IF NOT EXISTS must_change_password BOOLEAN NOT NULL DEFAULT false;

COMMENT ON COLUMN users.must_change_password IS 'Forces user to change password on next login. Set true after password reset.';
