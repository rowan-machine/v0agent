-- Supabase Storage Setup for Meeting Uploads
-- Run this in Supabase Dashboard SQL Editor

-- 1. Create the storage bucket (if not exists)
INSERT INTO storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
VALUES (
    'meeting-uploads',
    'meeting-uploads',
    true,
    52428800,  -- 50MB limit
    ARRAY['image/png', 'image/jpeg', 'image/gif', 'image/webp', 'application/pdf']::text[]
)
ON CONFLICT (id) DO NOTHING;

-- 2. Create storage policy to allow authenticated uploads
CREATE POLICY "Allow authenticated uploads" ON storage.objects
FOR INSERT TO authenticated
WITH CHECK (bucket_id = 'meeting-uploads');

-- 3. Create storage policy to allow public reads
CREATE POLICY "Allow public reads" ON storage.objects
FOR SELECT TO public
USING (bucket_id = 'meeting-uploads');

-- 4. Create storage policy for anon key uploads (for API)
CREATE POLICY "Allow anon uploads" ON storage.objects
FOR INSERT TO anon
WITH CHECK (bucket_id = 'meeting-uploads');

-- 5. Allow anon to update/delete their own files
CREATE POLICY "Allow anon manage" ON storage.objects
FOR ALL TO anon
USING (bucket_id = 'meeting-uploads')
WITH CHECK (bucket_id = 'meeting-uploads');

-- 6. Add columns to attachments table for Supabase URLs
ALTER TABLE attachments ADD COLUMN IF NOT EXISTS supabase_url TEXT;
ALTER TABLE attachments ADD COLUMN IF NOT EXISTS supabase_path TEXT;
