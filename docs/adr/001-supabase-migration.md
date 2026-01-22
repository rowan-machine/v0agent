# ADR-001: Migrate from SQLite to Supabase

## Status

Accepted

## Date

2026-01-22

## Context

SignalFlow started as a single-user desktop application using SQLite for local storage. As the product evolved, we identified several limitations:

1. **Multi-device access**: Users want to access their data from multiple devices
2. **Mobile support**: A mobile app requires cloud data access
3. **Real-time sync**: Changes should propagate instantly across devices
4. **Vector search**: Growing need for semantic search via embeddings
5. **Data persistence**: Risk of data loss with local-only storage

## Decision

Migrate the data layer from SQLite to Supabase PostgreSQL with the following approach:

1. **Phased migration**: Dual-write period → Read migration → Full cutover
2. **Schema design**: UUID primary keys, user_id foreign keys, RLS policies
3. **pgvector extension**: For embedding storage and similarity search
4. **Real-time subscriptions**: For instant cross-device sync
5. **Row Level Security**: Every table gets RLS with user-scoped policies

### Schema Parity

All 28 SQLite tables migrated to Supabase with equivalent or improved schemas:
- Core: meetings, documents, tickets, dikw_items, embeddings
- Career: career_profiles, career_suggestions, skill_tracker, standup_updates
- Knowledge: entity_links, dikw_evolution, ai_memory
- Analytics: mode_sessions, mode_statistics, archived_mode_sessions
- Supporting: attachments, settings, workflow_modes, and more

## Consequences

### Positive

- ✅ Multi-device access with real-time sync
- ✅ Native vector search with pgvector (IVFFlat indexing)
- ✅ Built-in authentication and RLS
- ✅ Automatic backups and point-in-time recovery
- ✅ Edge functions for serverless compute
- ✅ Mobile app can use same data layer

### Negative

- ⚠️ Requires internet connection for full functionality
- ⚠️ Monthly costs based on usage (~$25/month for Pro tier)
- ⚠️ Vendor lock-in to Supabase (mitigated by standard PostgreSQL)
- ⚠️ Migration complexity during transition period

### Neutral

- SQLite remains for offline-first mobile caching
- Service role key needed for server-side operations
- Need to manage connection pooling for high load

## Alternatives Considered

### Alternative 1: Self-hosted PostgreSQL

**Pros**: Full control, no vendor lock-in
**Cons**: Operational burden, no built-in auth/realtime, higher complexity
**Decision**: Rejected due to operational overhead

### Alternative 2: Firebase/Firestore

**Pros**: Real-time sync, mobile SDKs, generous free tier
**Cons**: NoSQL limitations, no native vector search, different query model
**Decision**: Rejected due to lack of vector search and SQL capabilities

### Alternative 3: PlanetScale (MySQL)

**Pros**: Serverless MySQL, branching, good DX
**Cons**: No native vector search, would need separate vector DB
**Decision**: Rejected due to lack of pgvector equivalent

## References

- [Supabase Documentation](https://supabase.com/docs)
- [pgvector Extension](https://github.com/pgvector/pgvector)
- [SUPABASE_MIGRATION_PLAN.md](../SUPABASE_MIGRATION_PLAN.md)
- [PHASED_MIGRATION_ROLLOUT.md](../../PHASED_MIGRATION_ROLLOUT.md)
