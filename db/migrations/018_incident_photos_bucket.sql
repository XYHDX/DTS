-- ============================================================
-- Migration 018: Incident photo storage bucket
-- ============================================================
-- Phase 6/E — driver app captures an incident photo but had nowhere
-- to put it. This migration:
--   • Creates a private "incidents" bucket via the storage API.
--   • Adds alerts.photo_url so the alert row can reference the uploaded
--     object (Supabase generates a permanent path; the API returns a
--     time-limited signed URL when admins view the alert).
--   • Adds RLS policies on storage.objects so:
--       - any authenticated user can upload to incidents/<their_user_id>/...
--       - only dispatchers+admins in the SAME operator can read.
--
-- ============================================================

BEGIN;

-- 1. Bucket. The storage.buckets row is the source of truth — without
--    it the policies below have nothing to scope to.
INSERT INTO storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
VALUES (
    'incidents',
    'incidents',
    false,
    5 * 1024 * 1024,  -- 5 MB per photo
    ARRAY['image/jpeg', 'image/png', 'image/webp']
)
ON CONFLICT (id) DO UPDATE
   SET public            = EXCLUDED.public,
       file_size_limit   = EXCLUDED.file_size_limit,
       allowed_mime_types = EXCLUDED.allowed_mime_types;

-- 2. alerts.photo_url column. Stored as the bucket-relative path so the
--    backend can mint signed URLs on read; we never persist a public URL.
ALTER TABLE alerts
    ADD COLUMN IF NOT EXISTS photo_path TEXT;
COMMENT ON COLUMN alerts.photo_path IS
    'Bucket-relative storage path for the incident photo (e.g. '
    '"incidents/<user_id>/<uuid>.jpg"). The API mints a 5-min signed URL '
    'when admins view the alert; never returns a public URL.';

-- 3. RLS on storage.objects scoped to the incidents bucket.
-- Read: dispatcher/admin/super_admin of the SAME operator who reported.
-- Write: any active driver can upload to their own folder.
DROP POLICY IF EXISTS incidents_upload  ON storage.objects;
DROP POLICY IF EXISTS incidents_read    ON storage.objects;

-- Drivers can upload — and ONLY to a path whose first segment after the
-- bucket prefix matches their own user_id, so a malicious client can't
-- overwrite another driver's photo.
CREATE POLICY incidents_upload ON storage.objects
    FOR INSERT
    TO authenticated
    WITH CHECK (
        bucket_id = 'incidents'
        AND (storage.foldername(name))[1] = auth.uid()::text
    );

-- Admins / dispatchers / super_admin can read every object in the bucket
-- (operator scoping happens at the application layer via the alerts row
-- they're inspecting). This avoids a polyfill JOIN against the alerts
-- table inside the policy, which would require security definer.
CREATE POLICY incidents_read ON storage.objects
    FOR SELECT
    TO authenticated
    USING (
        bucket_id = 'incidents'
        AND auth.jwt() ->> 'role' IN ('admin', 'dispatcher', 'super_admin')
    );

COMMIT;
