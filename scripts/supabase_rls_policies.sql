-- Supabase Row Level Security (RLS) Policies
-- Run this in the Supabase SQL Editor

-- Enable RLS on all tables
ALTER TABLE meetings ENABLE ROW LEVEL SECURITY;
ALTER TABLE documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE tickets ENABLE ROW LEVEL SECURITY;
ALTER TABLE test_plans ENABLE ROW LEVEL SECURITY;
ALTER TABLE conversations ENABLE ROW LEVEL SECURITY;
ALTER TABLE messages ENABLE ROW LEVEL SECURITY;
ALTER TABLE notifications ENABLE ROW LEVEL SECURITY;
ALTER TABLE settings ENABLE ROW LEVEL SECURITY;
ALTER TABLE sprint_settings ENABLE ROW LEVEL SECURITY;

-- For a single-user system (like this personal productivity app),
-- we create permissive policies that allow all operations.
-- In production with multiple users, you'd add user_id columns and
-- restrict based on auth.uid()

-- Meetings table policies
CREATE POLICY "Allow all operations on meetings"
ON meetings FOR ALL
USING (true)
WITH CHECK (true);

-- Documents table policies
CREATE POLICY "Allow all operations on documents"
ON documents FOR ALL
USING (true)
WITH CHECK (true);

-- Tickets table policies
CREATE POLICY "Allow all operations on tickets"
ON tickets FOR ALL
USING (true)
WITH CHECK (true);

-- Test plans table policies
CREATE POLICY "Allow all operations on test_plans"
ON test_plans FOR ALL
USING (true)
WITH CHECK (true);

-- Conversations table policies
CREATE POLICY "Allow all operations on conversations"
ON conversations FOR ALL
USING (true)
WITH CHECK (true);

-- Messages table policies
CREATE POLICY "Allow all operations on messages"
ON messages FOR ALL
USING (true)
WITH CHECK (true);

-- Notifications table policies
CREATE POLICY "Allow all operations on notifications"
ON notifications FOR ALL
USING (true)
WITH CHECK (true);

-- Settings table policies
CREATE POLICY "Allow all operations on settings"
ON settings FOR ALL
USING (true)
WITH CHECK (true);

-- Sprint settings table policies
CREATE POLICY "Allow all operations on sprint_settings"
ON sprint_settings FOR ALL
USING (true)
WITH CHECK (true);

-- NOTE: For a multi-user setup, you would:
-- 1. Add a user_id column to each table
-- 2. Replace policies with:
--    CREATE POLICY "Users can only access own data"
--    ON table_name FOR ALL
--    USING (user_id = auth.uid())
--    WITH CHECK (user_id = auth.uid());

-- API Key Access
-- The service role key bypasses RLS
-- The anon key respects RLS policies
-- For server-to-server, use service role key
-- For client-side, use anon key with proper policies
