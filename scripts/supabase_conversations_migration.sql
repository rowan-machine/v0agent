-- Migration: Add conversations and messages tables to Supabase
-- Run this in your Supabase SQL editor

-- =====================
-- CONVERSATIONS
-- =====================

-- Drop existing table if you want a fresh start (CAUTION: loses data)
-- drop table if exists public.messages cascade;
-- drop table if exists public.conversations cascade;

-- Create table
create table if not exists public.conversations (
  id uuid primary key default gen_random_uuid(),
  user_id uuid,  -- Optional: link to auth.users if using Supabase Auth
  title text,
  summary text,
  archived boolean default false,
  meeting_id uuid,  -- Reference to meetings table (if exists)
  document_id uuid,  -- Reference to documents table (if exists)
  -- Sync metadata
  device_id text,
  synced_at timestamptz default now(),
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);

-- Add columns if they don't exist (for existing tables)
DO $$ 
BEGIN
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'conversations' AND column_name = 'meeting_id') THEN
    ALTER TABLE public.conversations ADD COLUMN meeting_id uuid;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'conversations' AND column_name = 'document_id') THEN
    ALTER TABLE public.conversations ADD COLUMN document_id uuid;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'conversations' AND column_name = 'archived') THEN
    ALTER TABLE public.conversations ADD COLUMN archived boolean default false;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'conversations' AND column_name = 'device_id') THEN
    ALTER TABLE public.conversations ADD COLUMN device_id text;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'conversations' AND column_name = 'synced_at') THEN
    ALTER TABLE public.conversations ADD COLUMN synced_at timestamptz default now();
  END IF;
END $$;

-- RLS: Users can only see their own conversations
alter table public.conversations enable row level security;

create policy "Users can view own conversations" on public.conversations
  for select using (auth.uid() = user_id);
create policy "Users can insert own conversations" on public.conversations
  for insert with check (auth.uid() = user_id);
create policy "Users can update own conversations" on public.conversations
  for update using (auth.uid() = user_id);
create policy "Users can delete own conversations" on public.conversations
  for delete using (auth.uid() = user_id);

-- Indexes (only create if column exists)
create index if not exists idx_conversations_user on public.conversations(user_id);
create index if not exists idx_conversations_updated on public.conversations(updated_at desc);

-- Create meeting_id index only if column exists
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'conversations' AND column_name = 'meeting_id') THEN
    CREATE INDEX IF NOT EXISTS idx_conversations_meeting ON public.conversations(meeting_id);
  END IF;
END $$;

-- =====================
-- MESSAGES
-- =====================
create table if not exists public.messages (
  id uuid primary key default gen_random_uuid(),
  conversation_id uuid references public.conversations(id) on delete cascade not null,
  role text not null check (role in ('user', 'assistant', 'system')),
  content text not null,
  run_id text,  -- LangSmith run ID for tracing
  -- Metadata
  created_at timestamptz default now()
);

-- RLS: Users can access messages through conversation ownership
alter table public.messages enable row level security;

create policy "Users can access own conversation messages" on public.messages
  for all using (
    exists (
      select 1 from public.conversations c 
      where c.id = messages.conversation_id 
      and c.user_id = auth.uid()
    )
  );

-- Indexes
create index if not exists idx_messages_conversation on public.messages(conversation_id);
create index if not exists idx_messages_created on public.messages(created_at);
create index if not exists idx_messages_run_id on public.messages(run_id) where run_id is not null;

-- =====================
-- ANONYMOUS ACCESS POLICY (for dev/demo without auth)
-- =====================
-- If you're using anon key access, add these policies:

-- For anonymous access (development/demo only)
create policy "Anon can view conversations" on public.conversations
  for select using (true);
create policy "Anon can insert conversations" on public.conversations
  for insert with check (true);
create policy "Anon can update conversations" on public.conversations
  for update using (true);

create policy "Anon can access messages" on public.messages
  for all using (true);

-- Comment out the above anon policies for production!
