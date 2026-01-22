# ADR-002: Offline-First Mobile Architecture

## Status

Accepted

## Date

2026-01-22

## Context

The SignalFlow mobile app needs to provide a reliable user experience even when network connectivity is poor or unavailable. Key requirements:

1. **Connectivity challenges**: Users may be in meetings, transit, or areas with poor signal
2. **Quick capture**: Standup updates and notes must be capturable instantly
3. **Data freshness**: When online, data should sync in real-time
4. **Conflict handling**: Multiple devices may edit the same records

## Decision

Implement an offline-first architecture with the following components:

### 1. Local-First Writes

All user actions write to a local queue before attempting network sync:

```typescript
// All mutations go through queueOperation
await syncService.queueOperation('standup_updates', 'insert', {
  content: 'Working on DIKW synthesis...',
  sprint_date: new Date().toISOString()
});
```

### 2. Sync Queue

Pending operations stored in encrypted SecureStore:

```typescript
interface SyncQueueItem {
  id: string;
  table: string;
  operation: 'insert' | 'update' | 'delete';
  data: Record<string, any>;
  timestamp: string;
  retries: number;
}
```

### 3. Background Sync

Queue processed automatically when online:
- Network state monitored via `@react-native-community/netinfo`
- Auto-sync triggered on network restoration
- Exponential backoff for failed operations
- Max 3 retries before items are flagged for review

### 4. Real-Time Subscriptions

When online, Supabase real-time channels provide instant updates:

```typescript
supabase
  .channel('meetings_changes')
  .on('postgres_changes', { event: '*', schema: 'public', table: 'meetings' }, 
    payload => handleRealtimeChange(payload))
  .subscribe();
```

### 5. Conflict Resolution

**Strategy**: Last-Write-Wins with `updated_at` timestamps

- Each record has `updated_at` timestamp
- Server rejects updates where `updated_at` is older than current
- Client refetches and can show conflict UI if needed

## Consequences

### Positive

- ✅ App works without internet - capture standups, view cached data
- ✅ Instant UI response - no waiting for network
- ✅ Real-time sync when online - changes propagate immediately
- ✅ Resilient to network failures - queue retries automatically
- ✅ Secure local storage via Expo SecureStore

### Negative

- ⚠️ Data may be stale when offline for extended periods
- ⚠️ Conflicts possible with concurrent edits (rare for single-user)
- ⚠️ Increased complexity in data layer
- ⚠️ Storage limits on device for large caches

### Neutral

- React Query handles caching and refetching
- Zustand stores sync state for UI feedback
- Full sync available as manual user action

## Alternatives Considered

### Alternative 1: Online-Only

**Pros**: Simpler architecture, always fresh data
**Cons**: Unusable without internet, poor UX in low-connectivity
**Decision**: Rejected - unacceptable UX

### Alternative 2: Full Local Database (SQLite/WatermelonDB)

**Pros**: Complete offline capability, complex queries
**Cons**: Sync complexity, schema migration challenges, larger bundle
**Decision**: Rejected - overkill for current needs, SecureStore sufficient

### Alternative 3: Service Worker Cache (Web)

**Pros**: Standard web technology, PWA support
**Cons**: Mobile app is React Native, not web
**Decision**: Not applicable

## References

- [Expo SecureStore](https://docs.expo.dev/versions/latest/sdk/securestore/)
- [React Query Offline Support](https://tanstack.com/query/latest/docs/framework/react/guides/offline)
- [Supabase Real-time](https://supabase.com/docs/guides/realtime)
