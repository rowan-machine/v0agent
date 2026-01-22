import { create } from 'zustand';

interface SyncState {
  isOnline: boolean;
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
  setOnline: (online: boolean) => void;
  setSyncing: (syncing: boolean) => void;
  setLastSync: (date: Date) => void;
  setPendingCount: (count: number) => void;
  recordChange: (table: string, event: string, record: any) => void;
  clearChanges: () => void;
}

export const useSyncStore = create<SyncState>((set, get) => ({
  isOnline: true, // Default to online - optimistic assumption
  isSyncing: false,
  lastSync: null,
  pendingCount: 0,
  recentChanges: [],

  setOnline: (online: boolean) => set({ isOnline: online }),
  
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
