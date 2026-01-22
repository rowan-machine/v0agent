import { create } from 'zustand';

interface SyncState {
  isSyncing: boolean;
  lastSync: Date | null;
  pendingCount: number;
  recentChanges: Array<{
    table: string;
    event: string;
    record: any;
    timestamp: Date;
  }>;
  
  // Actions
  setSyncing: (syncing: boolean) => void;
  setLastSync: (date: Date) => void;
  setPendingCount: (count: number) => void;
  recordChange: (table: string, event: string, record: any) => void;
  clearChanges: () => void;
}

export const useSyncStore = create<SyncState>((set, get) => ({
  isSyncing: false,
  lastSync: null,
  pendingCount: 0,
  recentChanges: [],

  setSyncing: (syncing: boolean) => set({ isSyncing: syncing }),
  
  setLastSync: (date: Date) => set({ lastSync: date }),
  
  setPendingCount: (count: number) => set({ pendingCount: count }),
  
  recordChange: (table: string, event: string, record: any) => {
    const { recentChanges } = get();
    const newChange = {
      table,
      event,
      record,
      timestamp: new Date(),
    };
    
    // Keep only last 50 changes
    const updated = [newChange, ...recentChanges].slice(0, 50);
    set({ recentChanges: updated });
  },
  
  clearChanges: () => set({ recentChanges: [] }),
}));
