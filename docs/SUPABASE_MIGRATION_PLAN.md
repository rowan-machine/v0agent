# Supabase Database Migration Plan

## Overview

Migrate SignalFlow from local SQLite to Supabase PostgreSQL for:
- Cloud-hosted data persistence
- Multi-device sync capability
- Real-time subscriptions
- Vector embeddings with pgvector
- Row Level Security (RLS)

## Current Schema (SQLite)

### Core Tables (Priority 1 - Migrate First)
| Table | Records | Description |
|-------|---------|-------------|
| `meeting_summaries` | Many | Meeting notes with signals |
| `docs` | Many | Documents/transcripts |
| `tickets` | Many | Sprint backlog items |
| `dikw_items` | Many | Knowledge pyramid items |
| `embeddings` | Many | Vector embeddings |

### Supporting Tables (Priority 2)
| Table | Records | Description |
|-------|---------|-------------|
| `signal_feedback` | Many | Thumbs up/down on signals |
| `signal_status` | Many | Signal approval state |
| `attachments` | Few | File attachments |
| `code_locker` | Many | Code snapshots per ticket |

### Configuration Tables (Priority 3)
| Table | Records | Description |
|-------|---------|-------------|
| `sprint_settings` | 1 | Sprint configuration |
| `career_profile` | 1 | User career info |
| `settings` | Few | App settings |
| `workflow_modes` | Few | Mode definitions |

### Analytics Tables (Priority 4)
| Table | Records | Description |
|-------|---------|-------------|
| `mode_sessions` | Many | Time tracking |
| `standup_updates` | Many | Daily standups |
| `career_suggestions` | Many | AI suggestions |
| `skill_tracker` | Many | Skill progress |

## Supabase Schema Design

### Phase 1: Core Tables with RLS

```sql
-- Enable pgvector extension for embeddings
create extension if not exists vector;

-- =====================
-- MEETINGS
-- =====================
create table public.meetings (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references auth.users(id) on delete cascade,
  meeting_name text not null,
  synthesized_notes text not null,
  meeting_date timestamptz,
  raw_text text,
  signals jsonb default '{}',  -- {decisions: [], action_items: [], blockers: [], risks: [], ideas: []}
  source_document_id uuid references public.documents(id) on delete set null,
  -- Sync metadata
  device_id text,
  synced_at timestamptz default now(),
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);

-- RLS: Users can only see their own meetings
alter table public.meetings enable row level security;
create policy "Users can view own meetings" on public.meetings
  for select using (auth.uid() = user_id);
create policy "Users can insert own meetings" on public.meetings
  for insert with check (auth.uid() = user_id);
create policy "Users can update own meetings" on public.meetings
  for update using (auth.uid() = user_id);
create policy "Users can delete own meetings" on public.meetings
  for delete using (auth.uid() = user_id);

-- Indexes
create index idx_meetings_user on public.meetings(user_id);
create index idx_meetings_date on public.meetings(meeting_date);
create index idx_meetings_signals on public.meetings using gin(signals);

-- =====================
-- DOCUMENTS
-- =====================
create table public.documents (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references auth.users(id) on delete cascade,
  source text not null,  -- filename or source name
  content text not null,
  document_date timestamptz,
  meeting_id uuid references public.meetings(id) on delete set null,
  -- Sync metadata
  device_id text,
  synced_at timestamptz default now(),
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);

alter table public.documents enable row level security;
create policy "Users can CRUD own documents" on public.documents
  for all using (auth.uid() = user_id);

create index idx_documents_user on public.documents(user_id);
create index idx_documents_meeting on public.documents(meeting_id);

-- =====================
-- TICKETS
-- =====================
create table public.tickets (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references auth.users(id) on delete cascade,
  ticket_id text not null,  -- external ID like JIRA-1234
  title text not null,
  description text,
  status text default 'backlog' check (status in ('backlog', 'todo', 'in_progress', 'in_review', 'blocked', 'done')),
  priority text,
  sprint_points integer default 0,
  in_sprint boolean default true,
  -- AI-generated content
  ai_summary text,
  implementation_plan text,
  task_decomposition jsonb,  -- [{task, status, notes}]
  tags text[],
  -- Sync metadata
  device_id text,
  synced_at timestamptz default now(),
  created_at timestamptz default now(),
  updated_at timestamptz default now(),
  -- Unique per user
  unique(user_id, ticket_id)
);

alter table public.tickets enable row level security;
create policy "Users can CRUD own tickets" on public.tickets
  for all using (auth.uid() = user_id);

create index idx_tickets_user on public.tickets(user_id);
create index idx_tickets_status on public.tickets(status);
create index idx_tickets_sprint on public.tickets(in_sprint) where in_sprint = true;

-- =====================
-- DIKW ITEMS (Knowledge Pyramid)
-- =====================
create table public.dikw_items (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references auth.users(id) on delete cascade,
  level text not null check (level in ('data', 'information', 'knowledge', 'wisdom')),
  content text not null,
  summary text,
  source_type text,  -- signal, ai_memory, manual, synthesis
  source_ref_ids uuid[],
  original_signal_type text,
  meeting_id uuid references public.meetings(id) on delete set null,
  tags text[],
  confidence real default 0.5,
  validation_count integer default 0,
  promoted_to uuid references public.dikw_items(id),
  promoted_at timestamptz,
  status text default 'active' check (status in ('active', 'archived', 'merged')),
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);

alter table public.dikw_items enable row level security;
create policy "Users can CRUD own DIKW items" on public.dikw_items
  for all using (auth.uid() = user_id);

create index idx_dikw_user on public.dikw_items(user_id);
create index idx_dikw_level on public.dikw_items(level);
create index idx_dikw_meeting on public.dikw_items(meeting_id);

-- =====================
-- EMBEDDINGS (Vector Search)
-- =====================
create table public.embeddings (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references auth.users(id) on delete cascade,
  ref_type text not null,  -- meeting, document, ticket, dikw
  ref_id uuid not null,
  model text not null default 'text-embedding-3-small',
  embedding vector(1536),  -- OpenAI embedding dimension
  content_hash text,  -- For detecting when re-embedding is needed
  created_at timestamptz default now(),
  updated_at timestamptz default now(),
  unique(ref_type, ref_id, model)
);

alter table public.embeddings enable row level security;
create policy "Users can CRUD own embeddings" on public.embeddings
  for all using (auth.uid() = user_id);

-- Vector similarity search index
create index idx_embeddings_vector on public.embeddings 
  using ivfflat (embedding vector_cosine_ops) with (lists = 100);
create index idx_embeddings_ref on public.embeddings(ref_type, ref_id);

-- =====================
-- SIGNAL FEEDBACK
-- =====================
create table public.signal_feedback (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references auth.users(id) on delete cascade,
  meeting_id uuid references public.meetings(id) on delete cascade,
  signal_type text not null,
  signal_text text not null,
  feedback text not null check (feedback in ('up', 'down')),
  include_in_chat boolean default true,
  notes text,
  created_at timestamptz default now(),
  unique(meeting_id, signal_type, signal_text)
);

alter table public.signal_feedback enable row level security;
create policy "Users can CRUD own feedback" on public.signal_feedback
  for all using (auth.uid() = user_id);

-- =====================
-- SPRINT SETTINGS
-- =====================
create table public.sprint_settings (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references auth.users(id) on delete cascade unique,
  sprint_start_date date not null,
  sprint_length_days integer default 14,
  sprint_name text,
  updated_at timestamptz default now()
);

alter table public.sprint_settings enable row level security;
create policy "Users can CRUD own sprint settings" on public.sprint_settings
  for all using (auth.uid() = user_id);

-- =====================
-- CAREER PROFILE
-- =====================
create table public.career_profiles (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references auth.users(id) on delete cascade unique,
  current_role text,
  target_role text,
  strengths text[],
  weaknesses text[],
  interests text[],
  goals text,
  skills jsonb default '{}',
  updated_at timestamptz default now()
);

alter table public.career_profiles enable row level security;
create policy "Users can CRUD own profile" on public.career_profiles
  for all using (auth.uid() = user_id);
```

### Phase 2: Real-time Subscriptions

```sql
-- Enable real-time for key tables
alter publication supabase_realtime add table public.meetings;
alter publication supabase_realtime add table public.tickets;
alter publication supabase_realtime add table public.dikw_items;
```

### Phase 3: Database Functions

```sql
-- Semantic search function
create or replace function search_embeddings(
  query_embedding vector(1536),
  match_threshold float default 0.7,
  match_count int default 10,
  filter_type text default null
)
returns table (
  id uuid,
  ref_type text,
  ref_id uuid,
  similarity float
)
language plpgsql
as $$
begin
  return query
  select
    e.id,
    e.ref_type,
    e.ref_id,
    1 - (e.embedding <=> query_embedding) as similarity
  from public.embeddings e
  where 
    e.user_id = auth.uid()
    and (filter_type is null or e.ref_type = filter_type)
    and 1 - (e.embedding <=> query_embedding) > match_threshold
  order by e.embedding <=> query_embedding
  limit match_count;
end;
$$;

-- Get DIKW hierarchy
create or replace function get_dikw_hierarchy(item_id uuid)
returns table (
  id uuid,
  level text,
  content text,
  depth int
)
language sql
as $$
  with recursive hierarchy as (
    select id, level, content, 0 as depth
    from public.dikw_items
    where id = item_id and user_id = auth.uid()
    
    union all
    
    select d.id, d.level, d.content, h.depth + 1
    from public.dikw_items d
    join hierarchy h on d.promoted_to = h.id
    where d.user_id = auth.uid()
  )
  select * from hierarchy order by depth;
$$;
```

## Migration Strategy

### Step 1: Setup Supabase Project
- [x] Create project (wluchuiyhggiigcuiaya)
- [x] Configure MCP connection
- [ ] Enable pgvector extension
- [ ] Create tables with RLS

### Step 2: Create Migration Scripts
- [ ] SQL migration files in /migrations
- [ ] Data export script (SQLite → JSON)
- [ ] Data import script (JSON → Supabase)

### Step 3: Dual-Write Period
- [ ] Add Supabase client to app
- [ ] Write to both SQLite and Supabase
- [ ] Verify data consistency

### Step 4: Read Migration
- [ ] Switch reads to Supabase
- [ ] Keep SQLite as fallback
- [ ] Monitor for issues

### Step 5: Cutover
- [ ] Disable SQLite writes
- [ ] Full Supabase operation
- [ ] Archive local SQLite

## API Changes Required

### New Endpoints
- `POST /api/auth/login` - Supabase auth
- `POST /api/auth/logout` - Supabase auth
- `GET /api/sync/status` - Sync status

### Modified Endpoints
All existing endpoints need user_id context from Supabase auth.

## Feature Flags

```json
{
  "enableSupabaseBackend": {
    "enabled": false,
    "environments": ["development"],
    "rolloutPercentage": 0
  },
  "enableSupabaseAuth": {
    "enabled": false,
    "environments": ["development"],
    "rolloutPercentage": 0
  }
}
```

## Timeline

| Phase | Duration | Description |
|-------|----------|-------------|
| Schema Design | Done | This document |
| Table Creation | 1 day | Run SQL migrations |
| Data Migration | 2 days | Export/import data |
| Dual-Write | 1 week | Test consistency |
| Cutover | 1 day | Switch to Supabase |

## Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| Data loss during migration | Keep SQLite backup, validate row counts |
| Performance regression | Index optimization, query analysis |
| Auth complexity | Start with anonymous, add auth later |
| RLS misconfiguration | Test policies thoroughly |
