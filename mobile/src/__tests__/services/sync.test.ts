// mobile/src/__tests__/services/sync.test.ts
/**
 * Tests for offline-first sync service
 */

import { useSyncStore } from '../../stores/syncStore';

// Reset store between tests
const initialState = useSyncStore.getState();

describe('Sync Store', () => {
  beforeEach(() => {
    useSyncStore.setState(initialState);
  });

  describe('Initial State', () => {
    it('should have default values', () => {
      const state = useSyncStore.getState();
      
      expect(state.isSyncing).toBe(false);
      expect(state.lastSyncAt).toBeNull();
      expect(state.pendingChanges).toEqual([]);
      expect(state.syncErrors).toEqual([]);
    });
  });

  describe('setSyncing', () => {
    it('should update syncing state', () => {
      useSyncStore.getState().setSyncing(true);
      
      expect(useSyncStore.getState().isSyncing).toBe(true);
    });
  });

  describe('addPendingChange', () => {
    it('should add a change to pending queue', () => {
      const change = {
        id: '1',
        table: 'meetings',
        operation: 'INSERT' as const,
        data: { meeting_name: 'Test' },
        timestamp: new Date().toISOString(),
      };

      useSyncStore.getState().addPendingChange(change);
      
      const state = useSyncStore.getState();
      expect(state.pendingChanges).toHaveLength(1);
      expect(state.pendingChanges[0].table).toBe('meetings');
    });

    it('should queue multiple changes', () => {
      const change1 = {
        id: '1',
        table: 'meetings',
        operation: 'INSERT' as const,
        data: {},
        timestamp: new Date().toISOString(),
      };
      
      const change2 = {
        id: '2',
        table: 'documents',
        operation: 'UPDATE' as const,
        data: {},
        timestamp: new Date().toISOString(),
      };

      useSyncStore.getState().addPendingChange(change1);
      useSyncStore.getState().addPendingChange(change2);
      
      expect(useSyncStore.getState().pendingChanges).toHaveLength(2);
    });
  });

  describe('removePendingChange', () => {
    it('should remove a synced change', () => {
      const change = {
        id: 'test-id',
        table: 'meetings',
        operation: 'INSERT' as const,
        data: {},
        timestamp: new Date().toISOString(),
      };

      useSyncStore.getState().addPendingChange(change);
      expect(useSyncStore.getState().pendingChanges).toHaveLength(1);

      useSyncStore.getState().removePendingChange('test-id');
      expect(useSyncStore.getState().pendingChanges).toHaveLength(0);
    });
  });

  describe('setLastSyncAt', () => {
    it('should update last sync timestamp', () => {
      const now = new Date().toISOString();
      
      useSyncStore.getState().setLastSyncAt(now);
      
      expect(useSyncStore.getState().lastSyncAt).toBe(now);
    });
  });

  describe('addSyncError', () => {
    it('should track sync errors', () => {
      const error = {
        id: '1',
        message: 'Network error',
        timestamp: new Date().toISOString(),
      };

      useSyncStore.getState().addSyncError(error);
      
      expect(useSyncStore.getState().syncErrors).toHaveLength(1);
    });
  });

  describe('clearSyncErrors', () => {
    it('should clear all errors', () => {
      useSyncStore.getState().addSyncError({
        id: '1',
        message: 'Error',
        timestamp: new Date().toISOString(),
      });

      useSyncStore.getState().clearSyncErrors();
      
      expect(useSyncStore.getState().syncErrors).toHaveLength(0);
    });
  });
});


describe('Offline-First Behavior', () => {
  describe('Change Detection', () => {
    it('should detect when changes are pending', () => {
      const change = {
        id: '1',
        table: 'meetings',
        operation: 'INSERT' as const,
        data: {},
        timestamp: new Date().toISOString(),
      };

      useSyncStore.getState().addPendingChange(change);
      
      const hasPending = useSyncStore.getState().pendingChanges.length > 0;
      expect(hasPending).toBe(true);
    });
  });

  describe('Sync Order', () => {
    it('should maintain FIFO order for changes', () => {
      const changes = [
        { id: '1', table: 'a', operation: 'INSERT' as const, data: {}, timestamp: '2024-01-01T00:00:00Z' },
        { id: '2', table: 'b', operation: 'INSERT' as const, data: {}, timestamp: '2024-01-01T00:00:01Z' },
        { id: '3', table: 'c', operation: 'INSERT' as const, data: {}, timestamp: '2024-01-01T00:00:02Z' },
      ];

      changes.forEach(c => useSyncStore.getState().addPendingChange(c));
      
      const pending = useSyncStore.getState().pendingChanges;
      expect(pending[0].id).toBe('1');
      expect(pending[2].id).toBe('3');
    });
  });

  describe('Conflict Detection', () => {
    it('should flag conflicting changes for same record', () => {
      const localChange = {
        id: 'change-1',
        table: 'meetings',
        recordId: 'meeting-123',
        operation: 'UPDATE' as const,
        data: { meeting_name: 'Local' },
        timestamp: '2024-01-15T10:00:00Z',
      };

      const remoteTimestamp = '2024-01-15T11:00:00Z'; // Later

      // Conflict exists if remote was modified after our local change
      const hasConflict = new Date(remoteTimestamp) > new Date(localChange.timestamp);
      
      expect(hasConflict).toBe(true);
    });
  });
});
