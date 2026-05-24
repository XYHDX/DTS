-- Migration 008 — user_devices
-- Backs the push-notification flow documented in
-- markdown-files/technical/Push_Notification_Flow.md.

BEGIN;

CREATE TABLE IF NOT EXISTS user_devices (
    id            UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id       UUID            NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    operator_id   UUID            NOT NULL REFERENCES operators(id) ON DELETE CASCADE,
    token         TEXT            NOT NULL,
    platform      TEXT            NOT NULL CHECK (platform IN ('android','ios','web')),
    is_active     BOOLEAN         NOT NULL DEFAULT TRUE,
    created_at    TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at    TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    last_seen_at  TIMESTAMPTZ,
    failure_count INTEGER         NOT NULL DEFAULT 0,
    UNIQUE (user_id, token)
);

CREATE INDEX IF NOT EXISTS ix_user_devices_op_user
    ON user_devices (operator_id, user_id);

-- Partial index — the broadcast path only ever cares about active devices.
CREATE INDEX IF NOT EXISTS ix_user_devices_active
    ON user_devices (operator_id, platform)
    WHERE is_active = TRUE;

-- Token refresh bumps updated_at; the broadcast pipeline writes last_seen_at.
CREATE OR REPLACE FUNCTION user_devices_touch_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS user_devices_touch_updated_at_trg ON user_devices;
CREATE TRIGGER user_devices_touch_updated_at_trg
    BEFORE UPDATE ON user_devices
    FOR EACH ROW
    EXECUTE FUNCTION user_devices_touch_updated_at();

COMMENT ON TABLE  user_devices               IS 'FCM / APNs registration tokens per user. See Push_Notification_Flow.md.';
COMMENT ON COLUMN user_devices.is_active     IS 'Flipped to FALSE after 3 consecutive UNREGISTERED responses; reactivated on next register call.';
COMMENT ON COLUMN user_devices.failure_count IS 'Consecutive UNREGISTERED responses from FCM/APNs. Reset on successful send.';

-- RLS: a user can read/write only their own devices; service role bypasses.
ALTER TABLE user_devices ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS user_devices_owner_read ON user_devices;
CREATE POLICY user_devices_owner_read ON user_devices
    FOR SELECT
    USING (user_id = (auth.uid()));

DROP POLICY IF EXISTS user_devices_owner_write ON user_devices;
CREATE POLICY user_devices_owner_write ON user_devices
    FOR ALL
    USING (user_id = (auth.uid()))
    WITH CHECK (user_id = (auth.uid()));

COMMIT;
