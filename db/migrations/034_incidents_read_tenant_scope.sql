-- ============================================================
-- 034: Tenant-scope incident-photo reads  (M3)
-- ============================================================
-- Migration 018's `incidents_read` policy granted EVERY admin/dispatcher/
-- super_admin read access to EVERY operator's incident photos (operator
-- isolation was deferred to "the application layer"). In a multi-operator
-- deployment, an admin of operator A who can guess/enumerate a storage path
-- could read operator B's incident imagery directly via the Storage API.
--
-- This re-scopes reads to the operator that owns the referencing alert, with a
-- super_admin bypass. The API's own read path mints signed URLs with the
-- SERVICE role (which bypasses RLS), so this change does NOT affect normal
-- admin photo viewing — it only constrains direct client-JWT access, and it
-- fails CLOSED (no operator claim ⇒ no access) for non-super admins.
--
-- NOTE: verify against your live bucket that `alerts.photo_path` is stored in
-- the same form as `storage.objects.name`. If your photo_path includes the
-- "incidents/" bucket prefix while storage.objects.name does not, adjust the
-- join accordingly. Because the app uses the service role, a too-strict join
-- only blocks direct client reads (safe), never the admin console.
-- ============================================================

BEGIN;

DROP POLICY IF EXISTS incidents_read ON storage.objects;

CREATE POLICY incidents_read ON storage.objects
    FOR SELECT
    TO authenticated
    USING (
        bucket_id = 'incidents'
        AND (
            (auth.jwt() ->> 'role') = 'super_admin'
            OR (
                (auth.jwt() ->> 'role') IN ('admin', 'dispatcher')
                AND EXISTS (
                    SELECT 1
                    FROM public.alerts a
                    WHERE a.photo_path = storage.objects.name
                      AND a.operator_id::text = (auth.jwt() ->> 'operator_id')
                )
            )
        )
    );

COMMIT;

-- Rollback (restores the 018 broad-read policy):
--   DROP POLICY IF EXISTS incidents_read ON storage.objects;
--   CREATE POLICY incidents_read ON storage.objects FOR SELECT TO authenticated
--     USING (bucket_id = 'incidents'
--            AND auth.jwt() ->> 'role' IN ('admin','dispatcher','super_admin'));
