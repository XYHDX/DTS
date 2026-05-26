-- ============================================================
-- Migration 003: Passenger Feedback System
-- Adds trip_feedback table for passenger ratings and reviews
-- ============================================================

-- ── Feedback categories enum ─────────────────────────────────────────────────
CREATE TYPE feedback_category AS ENUM (
    'punctuality',
    'cleanliness',
    'driver_behavior',
    'safety',
    'comfort',
    'overall'
);

-- ── Trip feedback table ──────────────────────────────────────────────────────
CREATE TABLE trip_feedback (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    trip_id         UUID NOT NULL REFERENCES trips(id) ON DELETE CASCADE,
    driver_id       UUID REFERENCES users(id) ON DELETE SET NULL,
    passenger_id    UUID REFERENCES users(id) ON DELETE SET NULL,  -- NULL = anonymous
    rating          SMALLINT NOT NULL CHECK (rating >= 1 AND rating <= 5),
    comment         TEXT,
    categories      feedback_category[] DEFAULT '{}',
    is_anonymous    BOOLEAN NOT NULL DEFAULT false,
    operator_id     UUID REFERENCES operators(id) ON DELETE SET NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_trip_feedback_trip     ON trip_feedback(trip_id);
CREATE INDEX idx_trip_feedback_driver   ON trip_feedback(driver_id);
CREATE INDEX idx_trip_feedback_passenger ON trip_feedback(passenger_id);
CREATE INDEX idx_trip_feedback_created  ON trip_feedback(created_at DESC);

-- Prevent duplicate feedback: one per passenger per trip (if logged in)
CREATE UNIQUE INDEX idx_trip_feedback_unique_passenger
    ON trip_feedback(trip_id, passenger_id)
    WHERE passenger_id IS NOT NULL;

-- ── Driver rating summary view ───────────────────────────────────────────────
CREATE OR REPLACE VIEW driver_rating_summary AS
SELECT
    driver_id,
    COUNT(*)::INTEGER                                AS total_reviews,
    ROUND(AVG(rating)::NUMERIC, 2)                  AS average_rating,
    COUNT(*) FILTER (WHERE rating = 5)::INTEGER      AS five_star,
    COUNT(*) FILTER (WHERE rating = 4)::INTEGER      AS four_star,
    COUNT(*) FILTER (WHERE rating = 3)::INTEGER      AS three_star,
    COUNT(*) FILTER (WHERE rating = 2)::INTEGER      AS two_star,
    COUNT(*) FILTER (WHERE rating = 1)::INTEGER      AS one_star,
    MAX(created_at)                                  AS last_reviewed_at
FROM trip_feedback
WHERE driver_id IS NOT NULL
GROUP BY driver_id;

-- ── RLS policies ─────────────────────────────────────────────────────────────
ALTER TABLE trip_feedback ENABLE ROW LEVEL SECURITY;

-- Anyone can read non-anonymous feedback (or see their own anonymous feedback)
CREATE POLICY trip_feedback_select ON trip_feedback
    FOR SELECT USING (
        is_anonymous = false
        OR passenger_id = auth.uid()
    );

-- Authenticated users can insert their own feedback
CREATE POLICY trip_feedback_insert ON trip_feedback
    FOR INSERT WITH CHECK (
        passenger_id = auth.uid()
        OR (is_anonymous = true AND passenger_id IS NULL)
    );

-- Admins can read all feedback (bypass RLS via service key in application)
