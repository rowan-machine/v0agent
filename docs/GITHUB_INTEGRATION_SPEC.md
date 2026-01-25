# GitHub Integration Feature Specification

## Overview

Replace the current "Analyzing codebase for AI implementation memories" functionality with a GitHub OAuth integration that allows users to:
1. Authenticate with GitHub
2. Select repositories they've worked on
3. Import repository data to update their skills development graph
4. Optionally populate completed projects bank or AI implementation memories
5. Refresh repos for continuous skill tracking with progress reports

---

## Core User Stories

### US-1: GitHub Authentication
> As a user, I want to connect my GitHub account so the system can access my repositories.

### US-2: Repository Selection
> As a user, I want to browse and select specific repositories I've contributed to for analysis.

### US-3: Skills Extraction
> As a user, I want the system to analyze my code to identify and track my technical skills.

### US-4: Import Destination Choice
> As a user, I want to choose whether imported data goes to my skills graph, projects bank, or AI memories.

### US-5: Refresh & Progress Reports
> As a user, I want to refresh my repos to see new skills added and track skill growth over time.

### US-6: Auto-Suggested Projects
> As a user, I want the agent to identify smaller projects within my repos based on commits and documentation.

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Frontend (Mobile/Web)                        │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌──────────────┐  │
│  │ GitHub Auth │ │ Repo Picker │ │Import Config│ │Refresh/Report│  │
│  └──────┬──────┘ └──────┬──────┘ └──────┬──────┘ └──────┬───────┘  │
└─────────┼───────────────┼───────────────┼───────────────┼──────────┘
          │               │               │               │
          ▼               ▼               ▼               ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         API Layer (FastAPI)                          │
│  ┌─────────────────────────────────────────────────────────────────┐│
│  │                   /api/github/*                                 ││
│  │  POST /auth/callback  GET /repos  POST /import  POST /refresh   ││
│  └─────────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────────┘
          │
          ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     GitHub Integration Service                       │
│  ┌────────────┐ ┌────────────┐ ┌────────────┐ ┌──────────────────┐ │
│  │OAuth Client│ │Repo Fetcher│ │Code Analyzer│ │Commit Processor │ │
│  └────────────┘ └────────────┘ └────────────┘ └──────────────────┘ │
└─────────────────────────────────────────────────────────────────────┘
          │
          ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      Analysis Pipeline                               │
│  ┌────────────────┐ ┌────────────────┐ ┌────────────────────────┐  │
│  │Skills Extractor│ │Project Detector│ │AI Memory Formatter     │  │
│  │ (Languages,    │ │ (Commits, PRs, │ │ (Implementation        │  │
│  │  Frameworks,   │ │  README, Docs) │ │  patterns, decisions)  │  │
│  │  Libraries)    │ │                │ │                        │  │
│  └────────────────┘ └────────────────┘ └────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
          │
          ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      Data Destinations                               │
│  ┌────────────────┐ ┌────────────────┐ ┌────────────────────────┐  │
│  │Skills Dev Graph│ │Completed       │ │AI Implementation       │  │
│  │ (progress      │ │Projects Bank   │ │Memories                │  │
│  │  tracking)     │ │ (portfolio)    │ │ (learnings)            │  │
│  └────────────────┘ └────────────────┘ └────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Database Schema

### New Tables

```sql
-- GitHub account connections
CREATE TABLE github_connections (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id),
    github_user_id TEXT NOT NULL,
    github_username TEXT NOT NULL,
    access_token TEXT NOT NULL,  -- Encrypted
    refresh_token TEXT,          -- Encrypted
    token_expires_at TIMESTAMP,
    scopes TEXT[],
    connected_at TIMESTAMP DEFAULT NOW(),
    last_sync_at TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE,
    UNIQUE(user_id, github_user_id)
);

-- Imported repositories
CREATE TABLE github_repositories (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    connection_id UUID NOT NULL REFERENCES github_connections(id),
    github_repo_id TEXT NOT NULL,
    repo_name TEXT NOT NULL,
    repo_full_name TEXT NOT NULL,
    description TEXT,
    primary_language TEXT,
    languages JSONB,              -- {language: bytes}
    topics TEXT[],
    stars INTEGER,
    forks INTEGER,
    is_fork BOOLEAN,
    is_private BOOLEAN,
    created_at TIMESTAMP,
    pushed_at TIMESTAMP,
    imported_at TIMESTAMP DEFAULT NOW(),
    last_analyzed_at TIMESTAMP,
    analysis_status TEXT DEFAULT 'pending',  -- pending, analyzing, completed, failed
    UNIQUE(connection_id, github_repo_id)
);

-- Extracted skills from repos
CREATE TABLE github_skills_extracted (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    repository_id UUID NOT NULL REFERENCES github_repositories(id),
    skill_name TEXT NOT NULL,
    skill_category TEXT NOT NULL,  -- language, framework, library, tool, pattern
    confidence_score DECIMAL(3,2),  -- 0.00 to 1.00
    evidence_count INTEGER,         -- Number of files/usages found
    first_detected_at TIMESTAMP,
    last_seen_at TIMESTAMP,
    lines_of_code INTEGER,
    file_examples TEXT[],           -- Sample file paths
    UNIQUE(repository_id, skill_name)
);

-- Skill progression history
CREATE TABLE skill_progression (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id),
    skill_name TEXT NOT NULL,
    level_before INTEGER,
    level_after INTEGER,
    delta INTEGER,
    trigger_type TEXT,           -- github_import, github_refresh, meeting, manual
    trigger_id UUID,             -- Reference to github_repositories.id or meetings.id
    calculated_at TIMESTAMP DEFAULT NOW()
);

-- Detected sub-projects within repos
CREATE TABLE github_subprojects (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    repository_id UUID NOT NULL REFERENCES github_repositories(id),
    name TEXT NOT NULL,
    description TEXT,
    detected_type TEXT,          -- feature, module, migration, refactor, integration
    evidence_source TEXT,        -- commits, directory, docs, readme
    key_commits TEXT[],
    key_files TEXT[],
    technologies TEXT[],
    complexity_estimate TEXT,    -- small, medium, large
    suggested_for TEXT[],        -- ['completed_projects', 'ai_memories']
    auto_suggested BOOLEAN DEFAULT TRUE,
    user_accepted BOOLEAN,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Import history for tracking refresh reports
CREATE TABLE github_import_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    connection_id UUID NOT NULL REFERENCES github_connections(id),
    repository_id UUID REFERENCES github_repositories(id),  -- NULL for full refresh
    import_type TEXT NOT NULL,   -- initial, refresh, full_refresh
    started_at TIMESTAMP DEFAULT NOW(),
    completed_at TIMESTAMP,
    status TEXT DEFAULT 'running',  -- running, completed, failed
    
    -- Statistics
    repos_analyzed INTEGER,
    new_skills_found INTEGER,
    skills_increased INTEGER,
    new_projects_detected INTEGER,
    
    -- Report data
    report_summary JSONB,        -- Full report for display
    error_message TEXT
);
```

### Updates to Existing Tables

```sql
-- Add GitHub source tracking to skills
ALTER TABLE user_skills ADD COLUMN source_type TEXT;  -- meeting, github, manual
ALTER TABLE user_skills ADD COLUMN github_repository_id UUID REFERENCES github_repositories(id);

-- Add GitHub source to completed projects
ALTER TABLE completed_projects ADD COLUMN github_repository_id UUID REFERENCES github_repositories(id);
ALTER TABLE completed_projects ADD COLUMN github_subproject_id UUID REFERENCES github_subprojects(id);

-- Add GitHub source to AI memories
ALTER TABLE ai_memories ADD COLUMN github_repository_id UUID REFERENCES github_repositories(id);
ALTER TABLE ai_memories ADD COLUMN github_subproject_id UUID REFERENCES github_subprojects(id);
```

---

## API Endpoints

### Authentication

```
POST /api/github/auth/initiate
→ Returns GitHub OAuth URL with state token

GET /api/github/auth/callback
→ Handles OAuth callback, stores tokens, returns connection status

DELETE /api/github/auth/disconnect
→ Revokes tokens and removes connection
```

### Repository Management

```
GET /api/github/repos
→ Lists user's GitHub repositories (both connected and available)
Query params: ?connected_only=true&language=python&sort=pushed

POST /api/github/repos/import
Body: { 
  repository_ids: [string],
  import_to: ["skills_graph", "completed_projects", "ai_memories"],
  auto_detect_subprojects: boolean
}
→ Queues repos for analysis and import

GET /api/github/repos/{repo_id}/status
→ Returns analysis status and preliminary findings
```

### Refresh & Reports

```
POST /api/github/refresh
Body: {
  repository_ids?: [string],  // Omit for all connected repos
  since?: datetime            // Analyze changes since date
}
→ Triggers re-analysis of repos

GET /api/github/reports/latest
→ Returns the most recent refresh report

GET /api/github/reports/{report_id}
→ Returns specific report details
```

### Sub-projects

```
GET /api/github/repos/{repo_id}/subprojects
→ Lists detected sub-projects within a repo

POST /api/github/subprojects/{subproject_id}/import
Body: {
  import_to: "completed_projects" | "ai_memories",
  custom_name?: string,
  custom_description?: string
}
→ Imports a sub-project to selected destination

POST /api/github/subprojects/{subproject_id}/dismiss
→ Marks sub-project as not relevant
```

---

## Analysis Pipeline

### 1. Repository Fetcher
```python
class GitHubRepoFetcher:
    """Fetches repository metadata and content from GitHub API"""
    
    async def fetch_repo_metadata(self, repo_full_name: str) -> RepoMetadata:
        """Get basic repo info: languages, topics, stats"""
        
    async def fetch_repo_languages(self, repo_full_name: str) -> Dict[str, int]:
        """Get language breakdown in bytes"""
        
    async def fetch_repo_tree(self, repo_full_name: str, sha: str = "HEAD") -> List[TreeEntry]:
        """Get full file tree for analysis"""
        
    async def fetch_file_content(self, repo_full_name: str, path: str) -> str:
        """Fetch specific file content"""
        
    async def fetch_commits(self, repo_full_name: str, since: datetime = None) -> List[Commit]:
        """Get commit history, optionally since a date"""
```

### 2. Skills Extractor
```python
class SkillsExtractor:
    """Extracts skills from repository content"""
    
    # Detection rules by file type
    DETECTION_RULES = {
        "package.json": detect_npm_packages,
        "requirements.txt": detect_python_packages,
        "Cargo.toml": detect_rust_crates,
        "go.mod": detect_go_modules,
        "*.py": detect_python_imports,
        "*.ts": detect_typescript_patterns,
        # ... etc
    }
    
    async def extract_skills(self, repo: Repository) -> List[ExtractedSkill]:
        """Main extraction pipeline"""
        skills = []
        
        # 1. Language analysis
        skills.extend(self.analyze_languages(repo.languages))
        
        # 2. Dependency analysis
        skills.extend(await self.analyze_dependencies(repo))
        
        # 3. Pattern detection
        skills.extend(await self.analyze_code_patterns(repo))
        
        # 4. Framework detection
        skills.extend(await self.detect_frameworks(repo))
        
        return self.dedupe_and_score(skills)
    
    def calculate_confidence(self, skill: str, evidence: List[Evidence]) -> float:
        """Calculate confidence score based on evidence"""
        # Factors: frequency, recency, file diversity, usage patterns
```

### 3. Sub-project Detector
```python
class SubprojectDetector:
    """Identifies distinct projects/features within a repository"""
    
    async def detect_subprojects(self, repo: Repository) -> List[Subproject]:
        """Main detection pipeline"""
        subprojects = []
        
        # 1. Analyze commit history for feature branches/releases
        subprojects.extend(await self.analyze_commits(repo))
        
        # 2. Detect from directory structure
        subprojects.extend(await self.analyze_structure(repo))
        
        # 3. Parse README/CHANGELOG for feature descriptions
        subprojects.extend(await self.analyze_docs(repo))
        
        # 4. Identify migration/refactor patterns
        subprojects.extend(await self.detect_migrations(repo))
        
        return self.merge_and_dedupe(subprojects)
    
    async def analyze_commits(self, repo: Repository) -> List[Subproject]:
        """Group commits into logical projects"""
        # Use AI to cluster commits by purpose
        # Look for conventional commit prefixes (feat:, fix:, refactor:)
        # Identify PRs that represent complete features
```

### 4. AI Memory Formatter
```python
class AIMemoryFormatter:
    """Formats extracted data for AI implementation memories"""
    
    async def format_for_memories(
        self, 
        repo: Repository,
        skills: List[ExtractedSkill],
        subprojects: List[Subproject]
    ) -> List[AIMemory]:
        """Convert analysis to AI memory format"""
        memories = []
        
        # 1. Architecture decisions from code structure
        memories.extend(self.extract_architecture_patterns(repo))
        
        # 2. Implementation patterns from code
        memories.extend(self.extract_implementation_patterns(skills))
        
        # 3. Lessons from commit messages and docs
        memories.extend(self.extract_lessons(repo))
        
        return memories
```

---

## Skill Progression Tracking

### Progress Calculation Algorithm

```python
class SkillProgressionTracker:
    """Tracks skill level changes over time"""
    
    LEVEL_THRESHOLDS = {
        1: {"min_loc": 0, "min_projects": 1, "min_confidence": 0.2},
        2: {"min_loc": 500, "min_projects": 2, "min_confidence": 0.4},
        3: {"min_loc": 2000, "min_projects": 3, "min_confidence": 0.6},
        4: {"min_loc": 5000, "min_projects": 5, "min_confidence": 0.75},
        5: {"min_loc": 10000, "min_projects": 10, "min_confidence": 0.85},
    }
    
    def calculate_level(
        self,
        skill: str,
        total_loc: int,
        project_count: int,
        avg_confidence: float,
        recency_bonus: float = 0
    ) -> int:
        """Calculate skill level based on evidence"""
        
    def generate_progression_report(
        self,
        user_id: str,
        old_skills: Dict[str, int],
        new_skills: Dict[str, int]
    ) -> ProgressionReport:
        """Generate report comparing before/after"""
        return ProgressionReport(
            new_skills=[s for s in new_skills if s not in old_skills],
            improved_skills=[
                SkillDelta(skill=s, before=old_skills[s], after=new_skills[s])
                for s in new_skills 
                if s in old_skills and new_skills[s] > old_skills[s]
            ],
            total_skills_count=len(new_skills),
            summary=self.generate_summary_text(old_skills, new_skills)
        )
```

### Report Format

```json
{
  "report_id": "uuid",
  "generated_at": "2026-01-25T08:00:00Z",
  "repos_analyzed": 5,
  "summary": "Added 12 new skills and improved 8 existing skills",
  
  "new_skills": [
    {"name": "FastAPI", "category": "framework", "level": 3, "evidence": "15 files, 2,340 LOC"},
    {"name": "PostgreSQL", "category": "database", "level": 2, "evidence": "8 migrations, 45 queries"}
  ],
  
  "improved_skills": [
    {"name": "Python", "before": 3, "after": 4, "reason": "Additional 5,200 LOC across 3 repos"},
    {"name": "React", "before": 2, "after": 3, "reason": "New hooks patterns, 12 components"}
  ],
  
  "new_projects_detected": [
    {
      "name": "OAuth Integration",
      "repo": "my-app",
      "type": "feature",
      "technologies": ["OAuth2", "JWT", "Express"],
      "suggested_for": ["completed_projects"],
      "commit_range": "abc123..def456"
    }
  ],
  
  "auto_suggestions": {
    "to_completed_projects": 3,
    "to_ai_memories": 5
  }
}
```

---

## Security Considerations

### Token Storage
- All GitHub tokens encrypted at rest using AES-256
- Tokens stored in Supabase with RLS policies
- Refresh tokens used to minimize long-lived access

### Scopes Required
```
repo (read) - Access private repos
public_repo (read) - Access public repos
read:user - Get user profile
```

### Rate Limiting
- Respect GitHub API rate limits (5000/hour authenticated)
- Implement exponential backoff
- Queue large analysis jobs via background workers

### Privacy
- Users choose which repos to import
- Option to analyze only metadata (languages, topics) without code
- Clear data deletion when user disconnects

---

## Implementation Phases

### Phase 1: Foundation (Week 1)
- [ ] Database migrations for new tables
- [ ] GitHub OAuth flow implementation
- [ ] Basic repository listing API
- [ ] Token management and encryption

### Phase 2: Analysis Pipeline (Week 2)
- [ ] Skills extraction from languages
- [ ] Dependency file parsing
- [ ] Basic sub-project detection from commits
- [ ] Import to skills graph

### Phase 3: Advanced Analysis (Week 3)
- [ ] Code pattern detection
- [ ] AI-powered sub-project detection
- [ ] Import to projects bank and AI memories
- [ ] Confidence scoring refinement

### Phase 4: Refresh & Reporting (Week 4)
- [ ] Incremental refresh functionality
- [ ] Progress tracking and comparison
- [ ] Report generation
- [ ] UI polish and notifications

### Phase 5: Polish & Mobile (Week 5)
- [ ] Mobile app integration
- [ ] Performance optimization
- [ ] User feedback incorporation
- [ ] Documentation and tutorials

---

## File Structure

```
src/app/
├── services/
│   └── github/
│       ├── __init__.py
│       ├── oauth.py              # OAuth flow handling
│       ├── client.py             # GitHub API client
│       ├── fetcher.py            # Repo content fetcher
│       ├── skills_extractor.py   # Skills analysis
│       ├── subproject_detector.py# Sub-project detection
│       ├── memory_formatter.py   # AI memory formatting
│       └── progression.py        # Skill progression tracking
│
├── repositories/
│   └── github_repository.py      # Database operations
│
├── routes/
│   └── github.py                 # API endpoints
│
├── models/
│   └── github.py                 # Pydantic models
│
└── jobs/
    └── github_analysis.py        # Background analysis jobs
```

---

## Environment Variables

```env
# GitHub OAuth
GITHUB_CLIENT_ID=your_client_id
GITHUB_CLIENT_SECRET=your_client_secret
GITHUB_REDIRECT_URI=https://your-app.com/api/github/auth/callback

# Security
GITHUB_TOKEN_ENCRYPTION_KEY=your_32_byte_key

# Analysis Settings
GITHUB_MAX_REPO_SIZE_MB=100
GITHUB_ANALYSIS_CONCURRENCY=3
GITHUB_RATE_LIMIT_BUFFER=100
```

---

## UI/UX Considerations

### Mobile Flow
1. **Connect** → Tap "Connect GitHub" → Browser OAuth → Return to app
2. **Select** → Browse repos in list → Multi-select → Confirm
3. **Configure** → Choose import destinations → Start analysis
4. **Review** → View progress → See results → Accept suggestions
5. **Refresh** → Pull to refresh → View report → Track growth

### Key Screens
- GitHub connection management
- Repository browser with filters
- Import configuration modal
- Analysis progress indicator
- Refresh report with skill deltas
- Sub-project suggestion cards

---

## Success Metrics

- Time from connect to first skill import < 2 minutes
- Skill detection accuracy > 85%
- Sub-project detection relevance > 70% user acceptance
- Refresh completion < 30 seconds for incremental
- User engagement: > 60% refresh their repos monthly

---

## Open Questions

1. Should we support GitLab/Bitbucket in the future?
2. How do we handle very large repos (>100MB)?
3. Should sub-projects auto-import or require user confirmation?
4. How granular should skill levels be (5 vs 10 levels)?
5. Should we analyze forks differently than owned repos?

---

*Document Version: 1.0*  
*Created: January 25, 2026*  
*Author: Development Team*
