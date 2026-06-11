-- ============================================================
-- Migration 019: Vehicle operating-approval workflow
-- ============================================================
-- Implements the licensing flow requested by the Damascus Transit
-- operating model:
--
--   1. An OPERATOR staff account (role = dispatcher) registers a
--      vehicle (bus / microbus / taxi) and creates the driver's
--      username + password, then links the driver to the vehicle.
--   2. The vehicle starts in approval_status = 'pending' and CANNOT
--      operate: trip start, driver position reports, and telemetry
--      ingest are all rejected by the API until approval.
--   3. An ADMIN reviews the vehicle in /admin/approvals.html and
--      approves, rejects, or (later) suspends it. Every decision is
--      written to audit_log.
--
-- Existing vehicles are grandfathered as 'approved' (decision
-- 2026-06-11) so the live fleet keeps operating uninterrupted.
-- ============================================================

BEGIN;

-- 1) Approval state ------------------------------------------------
ALTER TABLE vehicles
  ADD COLUMN IF NOT EXISTS approval_status TEXT NOT NULL DEFAULT 'pending'
    CHECK (approval_status IN ('pending', 'approved', 'rejected', 'suspended')),
  ADD COLUMN IF NOT EXISTS approved_by UUID REFERENCES users(id) ON DELETE SET NULL,
  ADD COLUMN IF NOT EXISTS approved_at TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS approval_note TEXT,
  ADD COLUMN IF NOT EXISTS created_by UUID REFERENCES users(id) ON DELETE SET NULL;

-- 2) Grandfather the existing fleet --------------------------------
-- Every vehicle created before this migration keeps operating.
UPDATE vehicles
   SET approval_status = 'approved',
       approved_at     = now(),
       approval_note   = 'Grandfathered on migration 019 (pre-approval fleet)'
 WHERE approval_status = 'pending'
   AND created_at < now();

-- 3) Hot-path index -------------------------------------------------
-- The approvals queue filters by (operator_id, approval_status); the
-- ingest guard looks up approval_status by vehicle id (PK, already fast).
CREATE INDEX IF NOT EXISTS idx_vehicles_approval
    ON vehicles (operator_id, approval_status);

-- 4) Audit-log convenience view ------------------------------------
-- The admin approvals page shows the decision trail per vehicle.
CREATE OR REPLACE VIEW vehicle_approval_audit AS
SELECT a.id,
       a.admin_id,
       u.full_name  AS admin_name,
       a.action,
       a.details,
       a.created_at
  FROM audit_log a
  LEFT JOIN users u ON u.id = a.admin_id
 WHERE a.action IN ('vehicle_approved', 'vehicle_rejected',
                    'vehicle_suspended', 'vehicle_created',
                    'vehicle_resubmitted');

COMMIT;

-- Rollback:
--   DROP VIEW IF EXISTS vehicle_approval_audit;
--   DROP INDEX IF EXISTS idx_vehicles_approval;
--   ALTER TABLE vehicles
--     DROP COLUMN IF EXISTS approval_status,
--     DROP COLUMN IF EXISTS approved_by,
--     DROP COLUMN IF EXISTS approved_at,
--     DROP COLUMN IF EXISTS approval_note,
--     DROP COLUMN IF EXISTS created_by;
