-- ─── Migration 010 ──────────────────────────────────────────────────────────
-- Adds the columns the v4.1 backend writes to alerts:
--   • reported_by_user_id  — who triggered the alert (driver SOS, dispatcher,
--                            cron job). NULL means "system".
--   • resolved_at, resolved_by_user_id — set when /api/admin/alerts/{id}/resolve
--                            is called by an admin or dispatcher.
--
-- Idempotent: re-running this on a database that already has the columns is
-- a no-op. Safe to apply via the Supabase SQL editor.
-- ────────────────────────────────────────────────────────────────────────────

ALTER TABLE alerts
  ADD COLUMN IF NOT EXISTS reported_by_user_id uuid REFERENCES users(id),
  ADD COLUMN IF NOT EXISTS resolved_at         timestamptz,
  ADD COLUMN IF NOT EXISTS resolved_by_user_id uuid REFERENCES users(id);

CREATE INDEX IF NOT EXISTS idx_alerts_reported_by_user_id
  ON alerts (reported_by_user_id);
CREATE INDEX IF NOT EXISTS idx_alerts_resolved_by_user_id
  ON alerts (resolved_by_user_id);
CREATE INDEX IF NOT EXISTS idx_alerts_resolved_at
  ON alerts (resolved_at) WHERE resolved_at IS NOT NULL;

-- Audit trail: every resolution writes a timestamp + user. Combined with the
-- existing created_at on the row, this gives us full open→close history
-- without needing a separate audit table.

COMMENT ON COLUMN alerts.reported_by_user_id IS
  'User who created the alert (driver SOS, dispatcher, cron); NULL = system';
COMMENT ON COLUMN alerts.resolved_at IS
  'When the alert was resolved via PATCH /api/admin/alerts/{id}/resolve';
COMMENT ON COLUMN alerts.resolved_by_user_id IS
  'Dispatcher/admin who marked the alert resolved';

-- Add last_seen_at to users so /api/auth/login can update it on success.
-- The backend already tries to write this field (best-effort, wrapped in a
-- try/except), but until this column exists the write silently no-ops.
ALTER TABLE users
  ADD COLUMN IF NOT EXISTS last_seen_at timestamptz;
CREATE INDEX IF NOT EXISTS idx_users_last_seen_at
  ON users (last_seen_at DESC) WHERE last_seen_at IS NOT NULL;

COMMENT ON COLUMN users.last_seen_at IS
  'Updated on every successful /api/auth/login. Used by the admin Users page.';
