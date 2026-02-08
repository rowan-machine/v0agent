# V0Agent Cleanup & Bug Fix Backlog

> **Created**: 2026-01-28
> **Status**: Active Backlog
> **Purpose**: Consolidate remaining refactoring tasks and known bugs for systematic resolution

---

## 🐛 Active Bugs

### Dashboard Issues

| ID | Bug | Severity | Component | API Endpoint | Status |
|----|-----|----------|-----------|--------------|--------|
| BUG-001 | Sprint tickets not loading in mode panel | High | Dashboard | `/api/reports/sprint-burndown` | ✅ Fixed (missing credentials) |
| BUG-002 | "Could not load suggestions" / 500 error in Coach panel | High | Dashboard | `/api/career/suggestions` | ✅ Fixed (added backwards-compatible route) |
| BUG-003 | "Failed to fetch highlights" 500 error in Coach panel | High | Dashboard | `/api/dashboard/highlights` | ⚠️ Likely runtime/Supabase issue |
| BUG-004 | Code locker items not displaying | Medium | Dashboard | `/api/career/code-locker/files` | ✅ Fixed (missing credentials) |

### Career Development Issues

| ID | Bug | Severity | Component | API Endpoint | Status |
|----|-----|----------|-----------|--------------|--------|
| BUG-005 | "Failed to load tracker" on Development Tracker | High | Career | `/api/domains/career/tracker` | 🔴 Open |
| BUG-006 | "Failed to load skills" on Skill Development Graph | High | Career | `/api/domains/career/skills` | 🔴 Open |
| BUG-007 | Completed Projects Bank not syncing from tickets | Medium | Career | `/api/domains/career/projects/sync` | 🔴 Open |

### Notification Issues

| ID | Bug | Severity | Component | API Endpoint | Status |
|----|-----|----------|-----------|--------------|--------|
| BUG-008 | Notifications show on page but not in dashboard bell/dropdown | High | Notifications | `/api/notifications/count` | ✅ Fixed |

---

## 🔧 Refactoring Backlog

### Phase 5: Backend/Frontend Separation (Remaining)

#### 5.1 SDK Extraction ✅ COMPLETE
| Task | Status | Notes |
|------|--------|-------|
| Move SDK to `sdk/signalflow/` | ✅ Done | Already in correct location |
| Extract LangSmith client wrapper | ✅ Done | `analyst.py` exists |
| Create typed models with Pydantic | ✅ Done | `models.py` complete |
| Add async support | ✅ Done | `async_client.py` created |
| Package for PyPI | ✅ Done | `pyproject.toml`, `README.md`, `py.typed` |
| Add SDK unit tests | ✅ Done | `tests/test_client.py`, `test_async_client.py` |

#### 5.2 API Contracts ✅ COMPLETE
| Task | Status | Notes |
|------|--------|-------|
| OpenAPI spec generation | ✅ Done | `scripts/generate_openapi.py` |
| Response model validation | ✅ Done | `api/responses.py` |
| Error standardization | ✅ Done | `ErrorCode` enum |
| Version headers | ✅ Done | `api/versioning.py` |

#### 5.3 Mobile Client Updates (Remaining)
| Task | Status | Notes |
|------|--------|-------|
| Type generation from OpenAPI | ⬜ TODO | Auto-generate TypeScript types |
| Remove direct Supabase calls | ⬜ TODO | Use API endpoints only |
| Add offline support | ⬜ TODO | Queue operations when offline |

---

## 🏗️ Architecture Cleanup

### API Structure Rationalization

**Current State**: APIs are split between two locations:
```
src/app/api/
├── v1/               # Versioned REST API (preferred)
│   ├── meetings.py
│   ├── documents.py
│   ├── signals.py
│   ├── tickets.py
│   ├── notifications.py
│   └── ...
├── admin.py          # Legacy - no versioning
├── auth.py           # Legacy - no versioning
├── pages.py          # HTML template routes
├── pocket.py         # Legacy integration
└── ...
```

**Explanation**:
- `api/v1/` - Modern REST API with proper versioning, pagination, Pydantic models
- `api/*.py` - Legacy routes that predate versioning (auth, admin, pages, integrations)
- `domains/*/api/` - Domain-driven architecture (newer, coexists with v1)

**Recommended Actions**:
| Task | Priority | Notes |
|------|----------|-------|
| Migrate auth.py to v1 | Medium | Add `/api/v1/auth/*` routes |
| Migrate admin.py to v1 | Low | Add `/api/v1/admin/*` routes |
| Deprecate duplicate routes | Medium | career routes exist in both v1 and domains |
| Standardize on domains vs v1 | High | Pick one pattern going forward |

### UI Configuration System

**Location**: `src/app/ui/config.py`

**Purpose**: JSON-based UI configuration for swappable frontend implementations. Supports:
- Multiple frontends (Jinja2 templates, React, React Native)
- Theme switching (light/dark)
- Feature flags for UI elements
- Responsive layouts with breakpoints

**Config File**: `config/ui.json`

This system allows the backend to define UI structure without hardcoding frontend-specific implementations.

---

## 📝 Code Quality Issues (From VS Code Problems)

### GitHub Actions Secrets (Non-critical)
VS Code shows warnings about GitHub secrets - these are configuration warnings, not code errors. The secrets exist in GitHub repository settings.

### Notebook Linting (Low Priority)
| Issue | Count | Fix |
|-------|-------|-----|
| f-string without placeholders | ~15 | Change `f"string"` to `"string"` |
| Bare `except` clauses | ~3 | Change `except:` to `except Exception:` |
| Import order in cells | ~3 | Move imports to top of cell |
| Ambiguous variable `l` | ~2 | Rename to `level` |

---

## 🎯 Prioritized Action Plan

### Immediate (This Sprint)
1. **BUG-008**: Fix notification bell/dropdown - likely missing `link` field or count endpoint
2. **BUG-002/003**: Fix Coach panel 500 errors - investigate career suggestions and highlights endpoints
3. **BUG-001**: Fix sprint tickets in mode panel - check ticket filtering

### Short-term (Next Sprint)
4. **BUG-005/006**: Fix Career Development page tracker and skills
5. **BUG-004**: Fix Code locker display
6. **BUG-007**: Fix ticket sync to completed projects

### Medium-term
7. Complete Phase 5.3 (Mobile Client Updates)
8. Rationalize API structure (v1 vs domains)
9. Clean up notebook linting issues

---

## 📊 Bug Investigation Notes

### BUG-008: Notifications Bell/Dropdown Analysis

**Findings**:
1. Dashboard uses `/api/notifications` (legacy) - this returns **unactioned** notifications
2. Badge count comes from `/api/notifications/count` - this returns **unread** count
3. Notifications page at `/notifications` uses same API

**Root Cause Analysis**:
- The distinction between **unread** (`read_at IS NULL`) and **unactioned** (`actioned_at IS NULL`) may cause confusion
- Notifications can be unread but actioned (dismissed without reading)
- Notifications can be read but not actioned (viewed in dropdown but not clicked through)
- Badge should show unactioned count to match dropdown content

**Recommended Fix**:
1. Change `/api/notifications/count` to return unactioned count OR
2. Change dropdown to filter by unread status OR
3. Ensure consistency: what shows in dropdown = what the badge counts

**Files**:
- `src/app/api/notifications.py` - legacy endpoints
- `src/app/repositories/notifications_repository.py` - get_unread_count vs get_total_unactioned_count
- `src/app/templates/base.html` - lines 3360-3362 (count fetch), 3220-3245 (loadNotifications)

### Debugging Approach

1. **Check API endpoint directly**:
   ```bash
   curl -X GET http://localhost:8000/api/notifications?limit=10
   curl -X GET http://localhost:8000/api/notifications/count
   curl -X GET http://localhost:8000/api/dashboard/highlights
   ```

2. **Check server logs** for 500 errors:
   - Look for stack traces
   - Check Supabase query errors
   - Look for missing dependencies

3. **Compare working vs broken endpoints**:
   - Notifications page works → check if using different endpoint
   - Dashboard vs standalone pages may use different API calls

### Common Causes
- `neq None` instead of `not_.is_(None)` - PostgreSQL null comparisons
- Missing `by_category` parameter in skills graph
- Missing `link` field in notification responses
- Repository query errors not caught properly
- **Unread vs Unactioned mismatch** - badge/dropdown inconsistency

---

## 📋 Files to Review for Bugs

| Bug ID | Files to Check |
|--------|----------------|
| BUG-001 | `domains/tickets/api/items.py`, `domains/dashboard/api/` |
| BUG-002 | `domains/career/api/suggestions.py`, `api/v1/career_supabase_helper.py` |
| BUG-003 | `domains/dashboard/api/highlights.py` |
| BUG-004 | `domains/documents/api/`, dashboard template |
| BUG-005 | `domains/career/api/tracker.py` or similar |
| BUG-006 | `domains/career/api/skills.py` |
| BUG-007 | `domains/career/api/projects.py`, ticket sync logic |
| BUG-008 | `api/v1/notifications.py`, `api/notifications.py`, dashboard template |
