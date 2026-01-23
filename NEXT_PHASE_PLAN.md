# SignalFlow Next Phase: Strategic Roadmap 2026

**Status:** In Progress  
**Last Updated:** January 22, 2026  
**Previous Phase:** Migration Complete ✅  
**Focus:** High-Impact Features + Production Readiness

---

## Executive Summary

With the core migration complete (28 Supabase tables, agent system, mobile scaffold), the next phase focuses on **high-impact user features** that leverage our sophisticated architecture. Priority is given to features that create tangible workflow improvements for the primary user (Rowan).

**Strategic Priorities:**
1. ✅ **Import Pipeline** - Enable seamless Pocket → SignalFlow workflow (COMPLETE)
2. **Intelligent Notifications** - Proactive system that surfaces insights
3. **Automated Background Jobs** - System runs continuously, not just on-demand
4. ✅ **Enhanced Search** - Make all knowledge instantly accessible (COMPLETE)
5. **Modern Frontend** - Professional UX worthy of the sophisticated backend

---

## ✅ Completed Phases

### 🚀 Phase F1: Pocket Import Pipeline ✅ COMPLETE (112 tests)

| Feature | Tests | Endpoint | Description |
|---------|-------|----------|-------------|
| F1: Markdown Import | 30 | `POST /api/v1/imports/markdown` | Multi-format file upload (MD/PDF/DOCX/TXT) |
| F1b: Pocket Bundle Amend | 19 | `PATCH /api/v1/imports/{id}/amend` | Add Teams/Pocket transcripts to existing meetings |
| F1c: Mindmap Screenshot | 21 | `POST /api/v1/imports/mindmap/{id}` | GPT-4 Vision analysis + DIKW extraction |

**Mindmap Usage:** Upload separately via `POST /api/v1/imports/mindmap/{meeting_id}` with the screenshot file. The endpoint uses GPT-4 Vision to analyze the mindmap structure, extract patterns, and create DIKW knowledge items.

### 🔍 Phase F2: Enhanced Search ✅ COMPLETE (42 tests)

| Feature | Tests | Description |
|---------|-------|-------------|
| F2: Full-text Search | 20 | Search across `raw_text`, `meeting_documents`, highlight matches |
| F2b: Quick AI My Updates | 22 | `@Rowan` button searches transcripts for user mentions |

**F2b Features:**
- Searches for speaker timestamp format (e.g., "Rowan Neri 11:59 AM")
- Handles both first name and full name searches
- Extracts context snippets around mentions
- Uses `USER_NAME` env variable (defaults to "Rowan")

### 🔔 Phase F3: Notification API ✅ COMPLETE (22 tests)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/notifications` | GET | List pending notifications with type/limit filters |
| `/api/v1/notifications/unread-count` | GET | Badge count for UI bell |
| `/api/v1/notifications/{id}` | GET | Get single notification |
| `/api/v1/notifications/{id}/read` | PATCH | Mark notification as read |
| `/api/v1/notifications/{id}/action` | POST | Approve/reject/dismiss with feedback |
| `/api/v1/notifications/{id}` | DELETE | Remove notification |
| `/api/v1/notifications/mark-all-read` | POST | Mark all as read |
| `/api/v1/notifications/types/list` | GET | List available notification types |

**Notification Types:**
- `action_due` - Action item approaching deadline
- `transcript_match` - Grooming meeting matched to ticket
- `missed_criteria` - Items in meeting not reflected in ticket
- `mention` - User mentioned in transcript
- `coach` - Career growth suggestion
- `signal_review` - AI-extracted signal needs approval
- `dikw_synthesis` - Knowledge synthesis ready for review

---

## ✅ Phase F4: Background Jobs (31 tests) - COMPLETE

### F4a: 1:1 Prep Digest ✅ COMPLETE
**Schedule:** Biweekly Tuesday 7:00 AM (next: Jan 27, 2026)
**Service:** `src/app/services/background_jobs.py` - `OneOnOnePrepJob`

Generates notification answering:
1. What are my top 3 things I'm currently working on?
2. Where do I need help? (blockers from recent meetings)
3. What are my recent observations and feedback to discuss?
4. Potentially overdue actions (date pattern detection)

### F4d: Sprint Mode Auto-Detect ✅ COMPLETE
**Schedule:** Daily 8:00 AM + **On Page Load (Smart UI)**
**Service:** `src/app/services/background_jobs.py` - `SprintModeDetectJob`
**API:** `GET /api/settings/mode/suggested`
**Frontend:** Auto-switches mode on page load in `base.html`

Detects suggested workflow mode based on sprint cadence:
- **Mode A (Context Distillation):** 3-4 days before sprint, weekend prep
- **Mode B (Execution Ramp-up):** Mon-Tue of sprint week 1
- **Mode C (Deep Execution):** Wed-Fri week 1, Mon-Tue week 2
- **Mode D (Wrap-up):** Wed-Thu week 2

Sprint epoch: Jan 6, 2026 (14-day sprints starting Monday)

The floating mode button (top right) now:
- Auto-detects mode on page load via `/api/settings/mode/suggested`
- Pulses briefly when auto-switching modes
- Only notifies once per day about mode changes

### F4b: Stale Ticket / Blocker Alert ✅ COMPLETE
**Schedule:** Daily 9:00 AM (weekdays)
**Service:** `src/app/services/background_jobs.py` - `StaleTicketAlertJob`

Triggers when:
- Ticket has no activity for 5+ days
- Blocker mentioned but unresolved after 3 days

### F4c: Grooming-to-Ticket Match Alert ✅ COMPLETE
**Schedule:** Hourly (on new grooming meetings)
**Service:** `src/app/services/background_jobs.py` - `GroomingMatchJob`

Generates:
- Match notification with relevance score (ID match = 100%, keyword overlap scoring)
- Gap analysis: action items in meeting but not reflected in ticket
- Matches grooming, planning, refinement, backlog, sprint planning meetings

### F4e: Mode Completion Celebration ✅ COMPLETE
**Trigger:** On workflow checklist completion in dashboard
**APIs:**
- `GET /api/settings/mode/expected-duration` - Returns expected duration per mode
- `POST /api/workflow/check-completion` - Checks completion and creates celebration notification

Features:
- **Confetti Animation:** Triggers when completing all checkboxes before expected time
- **Historical Learning:** Expected durations blend 70% historical data + 30% defaults
- **Smart Defaults:** Each mode has sensible defaults (A=60m, B=45m, C=90m, D=60m, E=30m, F=20m, G=120m)
- **Time Saved Display:** Shows minutes saved ahead of schedule
- **Prevention of Repeats:** Only celebrates once per mode per day

The celebration system:
1. Frontend calls check-completion when all checkboxes complete
2. Backend compares elapsed time vs expected duration
3. If early, creates HIGH priority notification with `show_confetti: true`
4. Frontend shows confetti animation (100 particles, 3s fall) and toast

---

### F4f: Overdue Task Encouragement ✅ COMPLETE
**Schedule:** Weekdays at 2 PM and 5 PM (`0 14,17 * * 1-5`)
**APIs:**
- `GET /api/workflow/overdue-check` - Returns overdue status without creating notification
- `POST /api/workflow/send-encouragement` - Manually trigger encouragement notification

Features:
- **Overdue Detection:** Compares elapsed time vs expected duration with remaining tasks
- **Gut-Check Questions:** Mode-specific contextual questions with `{task_focus}` placeholder
- **Task Context Extraction:** Parses `task_decomposition` JSON and `implementation_plan` from tickets
- **Smart Encouragement:** Only triggers when overdue AND has unchecked tasks remaining

Gut-Check Templates per Mode:
- **Mode A (Context):** "How's the context gathering going? Any blockers on {task_focus}?"
- **Mode B (Planning):** "How are you feeling about the implementation approach for {task_focus}?"
- **Mode C (Draft Intake):** "How's the draft intake going? Need more context on {task_focus}?"
- **Mode D (Deep Review):** "How's the deep review progressing? Ready to decide on {task_focus}?"
- **Mode E (Promotion):** "How's the promotion readiness check going on {task_focus}?"
- **Mode F (Sync):** "How's the sync going? Any quick blockers on {task_focus}?"
- **Mode G (Transform):** "How are you feeling about the {task_focus} transform work?"

The encouragement system:
1. Background job runs at 2 PM and 5 PM weekdays
2. Checks if current mode session is overdue (elapsed > expected)
3. Verifies there are remaining unchecked tasks in workflow progress
4. Extracts task context from linked tickets (task_decomposition, implementation_plan)
5. Creates NORMAL priority notification with contextual gut-check question

---

## Phase Breakdown

#### 1.1 Multi-Format Import Endpoint
```python
# src/app/api/v1/imports.py (NEW)

from fastapi import APIRouter, UploadFile, File, HTTPException
from pydantic import BaseModel
from typing import Optional
import markdown
import PyPDF2
import docx

router = APIRouter(prefix="/api/v1/imports", tags=["imports"])

class ImportResult(BaseModel):
    meeting_id: str
    transcript_text: str
    signal_count: int
    warnings: list[str]

@router.post("/upload", response_model=ImportResult)
async def import_transcript(
    file: UploadFile = File(...),
    meeting_name: Optional[str] = None,
    source_url: Optional[str] = None,
    audio_file_url: Optional[str] = None
):
    """Import meeting transcript from Pocket export (markdown/PDF/DOCX/TXT)."""
    
    # Detect file type
    file_ext = file.filename.split('.')[-1].lower()
    
    # Extract text based on format
    if file_ext == 'md':
        text = extract_markdown(file)
    elif file_ext == 'pdf':
        text = extract_pdf(file)
    elif file_ext == 'docx':
        text = extract_docx(file)
    elif file_ext == 'txt':
        text = await file.read()
        text = text.decode('utf-8')
    else:
        raise HTTPException(400, "Unsupported file type")
    
    # Create meeting with metadata
    meeting_id = create_meeting_with_metadata(
        text=text,
        name=meeting_name or f"Imported from {file.filename}",
        source_url=source_url,
        audio_file_url=audio_file_url,
        import_source='pocket'
    )
    
    # Extract signals asynchronously
    signals = await extract_signals(meeting_id, text)
    
    return ImportResult(
        meeting_id=meeting_id,
        transcript_text=text,
        signal_count=len(signals),
        warnings=[]
    )
```

#### 1.2 Database Schema Changes
```sql
-- Add to meetings table
ALTER TABLE public.meetings ADD COLUMN source_url TEXT;
ALTER TABLE public.meetings ADD COLUMN audio_file_path TEXT;
ALTER TABLE public.meetings ADD COLUMN import_source TEXT DEFAULT 'manual';

CREATE INDEX idx_meetings_import_source ON public.meetings(import_source);

-- Import history table
CREATE TABLE public.import_history (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
  filename TEXT NOT NULL,
  file_type TEXT NOT NULL,
  meeting_id UUID REFERENCES public.meetings(id) ON DELETE SET NULL,
  status TEXT DEFAULT 'pending', -- pending, completed, failed
  error_message TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

ALTER TABLE public.import_history ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Users can view own imports" ON public.import_history
  FOR SELECT USING (auth.uid() = user_id);
```

#### 1.3 Supabase Storage Integration
```python
# Store audio files in Supabase Storage
from supabase import create_client

async def store_audio_file(file: UploadFile, meeting_id: str) -> str:
    """Store audio file in Supabase Storage and return URL."""
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    
    bucket_name = "meeting-audio"
    file_path = f"{meeting_id}/{file.filename}"
    
    # Upload to Supabase Storage
    supabase.storage.from_(bucket_name).upload(file_path, file.file)
    
    # Get public URL
    url = supabase.storage.from_(bucket_name).get_public_url(file_path)
    return url
```

**Estimated Effort:** 2-3 days  
**Dependencies:** None  
**User Benefit:** Immediate - transforms mobile workflow

---

### 🔔 Phase F2: Web-First Notification System (Impact: 90/100)

**Why This Matters:**
Right now, the system is reactive (user must check dashboard). Notifications make it **proactive**, surfacing insights when they matter.

**Notification Types (Priority Order):**

1. **🔴 Action Items Due** - "3 action items from Monday's standup are overdue"
2. **🟡 Transcript-Ticket Match** - "New transcript matches ticket JIRA-1234 (87% similarity)"
3. **🟢 Missed Criteria** - "Transcript mentions 'API rate limiting' but no ticket references it"
4. **🔵 @Rowan Mentioned** - "You were mentioned in 2 recent transcripts"
5. **⚪ Coach Recommendations** - "Weekly digest: 5 new career suggestions"

**Implementation:**

#### 2.1 Database Schema
```sql
CREATE TABLE public.notifications (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
  type TEXT NOT NULL CHECK (type IN ('action_due', 'transcript_match', 'missed_criteria', 'mention', 'coach')),
  title TEXT NOT NULL,
  body TEXT,
  data JSONB, -- {meeting_id: ..., ticket_id: ..., similarity: 0.87}
  read BOOLEAN DEFAULT FALSE,
  priority TEXT DEFAULT 'normal' CHECK (priority IN ('low', 'normal', 'high', 'critical')),
  created_at TIMESTAMPTZ DEFAULT NOW(),
  expires_at TIMESTAMPTZ DEFAULT (NOW() + INTERVAL '30 days'),
  action_url TEXT -- Deep link to relevant page
);

ALTER TABLE public.notifications ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Users can CRUD own notifications" ON public.notifications
  FOR ALL USING (auth.uid() = user_id);

CREATE INDEX idx_notifications_user_unread ON public.notifications(user_id, read) WHERE read = FALSE;
CREATE INDEX idx_notifications_priority ON public.notifications(priority, created_at DESC);
```

#### 2.2 API Endpoints
```python
# src/app/api/v1/notifications.py (NEW)

@router.get("/notifications", response_model=list[Notification])
async def get_notifications(
    unread_only: bool = False,
    limit: int = 50
):
    """Get user notifications."""
    # Query with filters
    # Return notifications ordered by priority, created_at DESC

@router.patch("/notifications/{id}/read")
async def mark_notification_read(id: str):
    """Mark notification as read."""
    # Update read=TRUE

@router.delete("/notifications/{id}")
async def dismiss_notification(id: str):
    """Dismiss/delete notification."""
    # Soft delete or hard delete based on preference
```

#### 2.3 UI Components

**Notification Bell in Top Nav:**
```html
<!-- src/app/templates/base.html -->
<div class="notification-bell" id="notificationBell">
  <svg><!-- bell icon --></svg>
  <span class="unread-badge" id="unreadCount">3</span>
</div>

<div class="notification-dropdown" id="notificationDropdown">
  <!-- Recent notifications -->
  <a href="/notifications">View all notifications →</a>
</div>
```

**Full Notifications Page:**
- `/notifications` - Inbox view with filters (unread, type, priority)
- Mark all as read button
- Notification item click navigates to action_url

**Estimated Effort:** 3-4 days  
**Dependencies:** None  
**User Benefit:** High - proactive system awareness

---

### ⏰ Phase F3: Scheduled Background Jobs (Impact: 85/100)

**Why This Matters:**
Notifications are useless without the intelligence to generate them. Background jobs enable **continuous, automated analysis**.

**Architecture Choice: Supabase pg_cron + Edge Functions**

**Rationale:**
- ✅ No extra infrastructure (no Celery/Redis needed)
- ✅ Native Postgres integration
- ✅ Supabase Edge Functions for Python/TypeScript logic
- ✅ Simple to manage and debug
- ⚠️ Limited to hourly granularity (fine for our use case)

**Implementation:**

#### 3.1 Enable pg_cron Extension
```sql
-- Run in Supabase SQL editor
CREATE EXTENSION IF NOT EXISTS pg_cron;

-- Grant access to edge functions
GRANT USAGE ON SCHEMA cron TO postgres;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA cron TO postgres;
```

#### 3.2 Job Definitions

**Job 1: Check Due Action Items (Daily 9 AM)**
```sql
SELECT cron.schedule(
  'check-due-actions',
  '0 9 * * *', -- 9 AM UTC daily
  $$
  SELECT net.http_post(
    'https://wluchuiyhggiigcuiaya.supabase.co/functions/v1/check-due-actions',
    '{"user_id": "all"}',
    '{"Content-Type": "application/json", "Authorization": "Bearer ' || current_setting('app.service_role_key') || '"}'
  )
  $$
);
```

**Edge Function: `check-due-actions`**
```typescript
// supabase/functions/check-due-actions/index.ts
import { serve } from "https://deno.land/std@0.168.0/http/server.ts"
import { createClient } from "https://esm.sh/@supabase/supabase-js@2"

serve(async (req) => {
  const supabase = createClient(
    Deno.env.get('SUPABASE_URL')!,
    Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!
  )
  
  // Find overdue action items
  const { data: signals } = await supabase
    .from('meetings')
    .select('signals')
    .contains('signals', { type: 'action_items' })
  
  // Parse and check due dates
  const overdueItems = parseOverdueActions(signals)
  
  // Create notifications
  for (const item of overdueItems) {
    await supabase.from('notifications').insert({
      user_id: item.user_id,
      type: 'action_due',
      title: 'Action Item Overdue',
      body: `"${item.text}" from ${item.meeting_name}`,
      priority: 'high',
      data: { meeting_id: item.meeting_id, signal_id: item.signal_id },
      action_url: `/meetings/${item.meeting_id}#${item.signal_id}`
    })
  }
  
  return new Response(JSON.stringify({ processed: overdueItems.length }))
})
```

**Job 2: Transcript-Ticket Matching (Hourly)**
```sql
SELECT cron.schedule(
  'match-transcripts',
  '0 * * * *', -- Every hour
  $$
  SELECT net.http_post(
    'https://wluchuiyhggiigcuiaya.supabase.co/functions/v1/match-transcripts',
    '{}',
    '{"Content-Type": "application/json", "Authorization": "Bearer ' || current_setting('app.service_role_key') || '"}'
  )
  $$
);
```

**Edge Function: `match-transcripts`**
```typescript
serve(async (req) => {
  const supabase = createClient(...)
  
  // Get recent unmatched transcripts
  const { data: meetings } = await supabase
    .from('meetings')
    .select('id, synthesized_notes, embeddings!inner(*)')
    .is('transcript_ticket_match', null)
    .gte('created_at', new Date(Date.now() - 3600000)) // Last hour
  
  // Get active tickets with embeddings
  const { data: tickets } = await supabase
    .from('tickets')
    .select('id, title, description, embeddings!inner(*)')
    .eq('status', 'in_progress')
  
  // For each meeting, find best matching ticket
  for (const meeting of meetings) {
    const matches = await findSimilarTickets(meeting, tickets)
    
    // If similarity > threshold (0.75), create notification
    if (matches[0]?.similarity > 0.75) {
      await supabase.from('notifications').insert({
        type: 'transcript_match',
        title: 'Transcript Matches Ticket',
        body: `"${meeting.synthesized_notes.slice(0,100)}..." matches ${matches[0].ticket_id}`,
        priority: 'normal',
        data: { meeting_id: meeting.id, ticket_id: matches[0].id, similarity: matches[0].similarity },
        action_url: `/meetings/${meeting.id}?suggest_ticket=${matches[0].id}`
      })
    }
  }
})
```

**Job 3: Detect @Mentions (Trigger-Based)**
```sql
-- Use Postgres trigger instead of cron for immediate detection
CREATE OR REPLACE FUNCTION notify_on_mention()
RETURNS TRIGGER AS $$
BEGIN
  IF NEW.synthesized_notes ~* 'rowan|@rowan' THEN
    INSERT INTO notifications (user_id, type, title, body, priority, data, action_url)
    VALUES (
      NEW.user_id,
      'mention',
      'You Were Mentioned',
      'Found "@Rowan" in ' || NEW.meeting_name,
      'high',
      json_build_object('meeting_id', NEW.id),
      '/meetings/' || NEW.id
    );
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER meeting_mention_trigger
  AFTER INSERT OR UPDATE OF synthesized_notes ON meetings
  FOR EACH ROW
  EXECUTE FUNCTION notify_on_mention();
```

**Job 4: Weekly Coach Digest (Sunday 6 PM)**
```sql
SELECT cron.schedule(
  'weekly-coach-digest',
  '0 18 * * 0', -- Sunday 6 PM UTC
  $$
  SELECT net.http_post(
    'https://wluchuiyhggiigcuiaya.supabase.co/functions/v1/weekly-coach-digest',
    '{}',
    '{"Content-Type": "application/json"}'
  )
  $$
);
```

**Configuration Table for Tunability:**
```sql
CREATE TABLE public.app_config (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL,
  description TEXT,
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

INSERT INTO app_config (key, value, description) VALUES
  ('transcript_match_threshold', '0.75', 'Minimum similarity for auto-match'),
  ('action_due_days', '3', 'Days before action item is considered overdue'),
  ('notification_retention_days', '30', 'Auto-archive notifications after N days');
```

**Estimated Effort:** 4-5 days  
**Dependencies:** F2 (Notification system)  
**User Benefit:** Very High - automated intelligence

---

### 🔍 Phase F4: Enhanced Semantic Search (Impact: 75/100)

**Why This Matters:**
Current search is limited to single entity types. Unified search across all knowledge is a **10x productivity multiplier**.

**Features:**

1. **Cross-Entity Search** - Single query searches meetings, tickets, documents, DIKW
2. **"My Mentions" Shortcut** - Pre-filter for @Rowan mentions
3. **Expandable Search Bar** - Top nav search expands inline (no page navigation)
4. **Saved Searches** - Store common queries ("blockers this sprint", "API decisions")
5. **Quick Actions** - Approve signal, create ticket, promote to DIKW from results

**Implementation:**

#### 4.1 Unified Search Endpoint
```python
# src/app/api/v1/search.py

@router.get("/search/unified")
async def unified_search(
    query: str,
    entity_types: list[str] = ["meetings", "tickets", "documents", "dikw"],
    limit: int = 20
):
    """Search across all entity types with semantic similarity."""
    
    # Generate query embedding
    query_embedding = await get_embedding(query)
    
    # Search each entity type in parallel
    results = await asyncio.gather(
        search_meetings(query_embedding, limit),
        search_tickets(query_embedding, limit),
        search_documents(query_embedding, limit),
        search_dikw(query_embedding, limit)
    )
    
    # Merge and re-rank results
    merged = merge_and_rank(results, query)
    
    return {
        "query": query,
        "total_results": len(merged),
        "results": merged[:limit],
        "filters": entity_types
    }
```

#### 4.2 UI Components

**Expandable Search Bar:**
```html
<!-- Top nav search -->
<div class="search-container" id="searchContainer">
  <input type="search" id="globalSearch" placeholder="Search everything...">
  <div class="search-results-dropdown" id="searchResults">
    <!-- Live search results appear here -->
  </div>
</div>

<script>
  // Debounced search-as-you-type
  const searchInput = document.getElementById('globalSearch');
  searchInput.addEventListener('input', debounce(async (e) => {
    const results = await fetch(`/api/v1/search/unified?query=${e.target.value}`);
    renderSearchResults(results);
  }, 300));
</script>
```

**Saved Searches:**
```sql
CREATE TABLE public.saved_searches (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  query TEXT NOT NULL,
  filters JSONB DEFAULT '{}',
  created_at TIMESTAMPTZ DEFAULT NOW()
);
```

**Estimated Effort:** 3 days  
**Dependencies:** None (uses existing embeddings)  
**User Benefit:** Medium-High - faster knowledge discovery

---

### 🎨 Phase F6: Modern Frontend Redesign (Impact: 80/100, Effort: HIGH)

**Why This Matters:**
Current Jinja2 templates are functional but **lack polish**. A modern React frontend would:
- Enable real-time updates without page refresh
- Support drag-drop for signals, tickets
- Inline editing everywhere
- Better mobile responsiveness
- Professional look for potential productization

**Recommended Stack:**
- **Next.js 14+** (App Router) - SSR/SSG, great DX
- **TypeScript** - Type safety
- **Tailwind CSS** - Consistent styling
- **shadcn/ui** - Beautiful, accessible components
- **React Query** - Data fetching with caching
- **Zustand** - Lightweight state management

**Architecture:**
```
┌─────────────────────────────────────────────────────────────┐
│                   Next.js Frontend (Vercel)                  │
├─────────────────────────────────────────────────────────────┤
│  /dashboard       - Main overview with real-time updates    │
│  /meetings        - List + detail views                      │
│  /meetings/[id]   - Individual meeting with signal actions   │
│  /tickets         - Kanban board with drag-drop              │
│  /search          - Unified search with live results         │
│  /notifications   - Notification inbox                       │
│  /career          - Career development hub                   │
│  /settings        - User settings                            │
└─────────────────────────────────────────────────────────────┘
                            ↓ API calls (fetch)
┌─────────────────────────────────────────────────────────────┐
│          FastAPI Backend (Railway/existing server)           │
│                    /api/v1/* endpoints                       │
└─────────────────────────────────────────────────────────────┘
```

**Phased Approach:**
1. **Phase 6A:** Build Next.js app with dashboard + meetings (2 weeks)
2. **Phase 6B:** Migrate tickets + search pages (1 week)
3. **Phase 6C:** Add career, settings, notifications (1 week)
4. **Phase 6D:** Polish + mobile responsive (3-4 days)

**Estimated Effort:** 4-5 weeks (if done all at once)  
**Dependencies:** None (can run in parallel with Jinja2 app)  
**User Benefit:** High - professional UX, better productivity

---

## Implementation Priority Matrix

| Priority | Item | Impact | Effort | Status |
|----------|------|--------|--------|--------|
| **P0** | ✅ F1: Pocket Import Pipeline | 95/100 | 2-3 days | **COMPLETE** (70 tests) |
| **P0** | ✅ F2: Enhanced Search | 90/100 | 2-3 days | **COMPLETE** (42 tests) |
| **P0** | ✅ F3: Notification API | 85/100 | 1 day | **COMPLETE** (22 tests) |
| **P1** | F4a: 1:1 Prep Job | 90/100 | 1 day | Next Priority |
| **P1** | F4b: Stale Ticket Alert | 80/100 | 1 day | After F4a |
| **P1** | F4c: Grooming Match Alert | 85/100 | 1-2 days | After F4b |
| **P2** | Test Coverage to 80% | 70/100 | 3-4 days | ~80% achieved (134 tests) |
| **P3** | F6: Next.js Frontend | 80/100 | 4-5 weeks | Month 2 |
| **P4** | MCP Tool Registry | 65/100 | 1 week | Month 3 |
| **P4** | F5: Mobile Features | 60/100 | 1 week | Month 3 |

**Execution Progress:**
- ✅ **Week 1-2:** F1 (Import) COMPLETE - Markdown/PDF import, Pocket bundle amend, Mindmap vision analysis
- ✅ **Week 2:** F2 (Search) COMPLETE - Full-text search, @Rowan mentions, highlight snippets
- ✅ **Week 3:** F3 (Notification API) COMPLETE - Full REST API with 22 tests
- 🔄 **Week 3-4:** F4 (Background Jobs) - 1:1 prep, stale alerts, grooming match
- **Month 2:** F6 (Frontend redesign) - big project
- **Month 3:** MCP integration + mobile polish

---

## Success Metrics

**By End of Phase F1-F3 ✅ COMPLETE:**
- [x] Rowan can import Pocket transcripts in <10 seconds
- [x] Multi-format support (MD, PDF, DOCX, TXT)
- [x] Mindmap screenshots analyzed via GPT-4 Vision
- [x] Search returns relevant results across meetings in <1s
- [x] @Rowan button surfaces personal mentions
- [x] Notification API ready for background jobs
- [x] 134 tests passing, ~80% coverage

**By End of Phase F4 (Target: Jan 27, 2026):**
- [ ] 1:1 prep digest delivered biweekly Tuesday AM
- [ ] Stale ticket/blocker alerts daily
- [ ] Grooming-to-ticket matching with gap analysis
- [ ] System sends 5+ notifications per week proactively

**By End of Phase F6 (Month 2):**
- [ ] Next.js frontend live in production
- [ ] Real-time updates working for meetings/tickets
- [ ] Mobile-responsive design passes lighthouse tests
- [ ] Page load times <500ms (cached)

**By End of MCP Integration (Month 3):**
- [ ] GitHub integration for ticket sync
- [ ] Notion integration for knowledge export
- [ ] Slack integration for notifications (optional)

---

## Risk Mitigation

| Risk | Mitigation Strategy |
|------|---------------------|
| **Supabase pg_cron limitations** | Fall back to external cron (Railway) if needed |
| **Next.js migration takes too long** | Build incrementally, keep Jinja2 as fallback |
| **Notification spam** | Add user preferences for notification types |
| **Poor search relevance** | Tune embedding model, add keyword fallback |
| **Mobile app complexity** | Focus on web first, mobile is companion only |

---

## Backlog (Deferred Items)

The following features are on the roadmap but deferred to future phases:

### Web Hosting & Deployment
**Status:** Deferred  
**Reason:** Focus on feature development first, then productionize

- Deploy FastAPI backend to Railway/Render/Fly.io
- Configure production Supabase instance
- Set up CI/CD pipeline for automated deployments
- Domain configuration and SSL
- CDN for static assets

### Database Encryption for Portability
**Status:** Deferred  
**Reason:** Current SQLite local-only use case doesn't require encryption

- Encrypt SQLite database at rest using SQLCipher
- Secure key management for portable database
- Support for encrypted Supabase connections
- Data export/import with encryption

### Responsive Mobile Design
**Status:** Deferred to Docs/KB Only  
**Reason:** Primary workflow is desktop; mobile is companion view only

- Responsive layouts for Documents/Knowledge Base pages
- Mobile-optimized search interface
- Touch-friendly navigation
- Offline-first PWA capabilities
- Push notifications (via PWA)

---

## Conclusion

This phase transforms SignalFlow from a **functional tool** to a **proactive intelligence system**. The import pipeline removes friction, notifications surface insights automatically, and the enhanced UX makes the system a joy to use daily.

**Next Steps:**
1. Review this plan with stakeholders (Rowan)
2. Prioritize F1-F4 for immediate execution
3. Start F1 (Pocket Import) on Monday
4. Iterate based on user feedback

---

*Context improved by Giga AI - Main overview, Migration Manifest, and Multi-Agent Architecture were used to create this strategic roadmap focusing on high-impact features for production readiness.*
