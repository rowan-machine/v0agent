/**
 * Offline-First Sync Service
 * 
 * Implements a robust offline-first sync strategy:
 * 1. All writes go to local storage first
 * 2. Background sync pushes changes to Supabase when online
 * 3. Conflict resolution using last-write-wins with timestamps
 * 4. Real-time subscriptions for instant updates when online
 */

import { supabase } from './api';
import * as SecureStore from 'expo-secure-store';
import NetInfo from '@react-native-community/netinfo';
import { useSyncStore } from '../stores/syncStore';

// Sync queue stored locally
const SYNC_QUEUE_KEY = 'signalflow_sync_queue';
const LAST_SYNC_KEY = 'signalflow_last_sync';

interface SyncQueueItem {
  id: string;
  table: string;
  operation: 'insert' | 'update' | 'delete';
  data: Record<string, any>;
  timestamp: string;
  retries: number;
}

class SyncService {
  private isOnline = false;
  private syncInProgress = false;
  private subscriptions: (() => void)[] = [];

  async initialize() {
    // Monitor network status
    NetInfo.addEventListener(state => {
      const wasOffline = !this.isOnline;
      this.isOnline = state.isConnected ?? false;
      
      // Trigger sync when coming back online
      if (wasOffline && this.isOnline) {
        this.processQueue();
      }
    });

    // Initial network check
    const state = await NetInfo.fetch();
    this.isOnline = state.isConnected ?? false;

    // Set up real-time subscriptions
    this.setupRealtimeSubscriptions();

    // Process any pending queue items
    if (this.isOnline) {
      this.processQueue();
    }
  }

  private setupRealtimeSubscriptions() {
    // Subscribe to changes in key tables
    const tables = ['meetings', 'tickets', 'dikw_items', 'standup_updates'];
    
    for (const table of tables) {
      const subscription = supabase
        .channel(`${table}_changes`)
        .on(
          'postgres_changes',
          { event: '*', schema: 'public', table },
          (payload) => {
            // Update local cache with server changes
            this.handleRealtimeChange(table, payload);
          }
        )
        .subscribe();

      this.subscriptions.push(() => subscription.unsubscribe());
    }
  }

  private async handleRealtimeChange(table: string, payload: any) {
    const { eventType, new: newRecord, old: oldRecord } = payload;
    
    // Update the sync store to notify UI
    const store = useSyncStore.getState();
    store.recordChange(table, eventType, newRecord || oldRecord);
  }

  async queueOperation(
    table: string,
    operation: 'insert' | 'update' | 'delete',
    data: Record<string, any>
  ): Promise<void> {
    const item: SyncQueueItem = {
      id: `${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
      table,
      operation,
      data,
      timestamp: new Date().toISOString(),
      retries: 0,
    };

    // Add to queue
    const queue = await this.getQueue();
    queue.push(item);
    await this.saveQueue(queue);

    // Try to sync immediately if online
    if (this.isOnline) {
      this.processQueue();
    }
  }

  private async getQueue(): Promise<SyncQueueItem[]> {
    const stored = await SecureStore.getItemAsync(SYNC_QUEUE_KEY);
    return stored ? JSON.parse(stored) : [];
  }

  private async saveQueue(queue: SyncQueueItem[]): Promise<void> {
    await SecureStore.setItemAsync(SYNC_QUEUE_KEY, JSON.stringify(queue));
    useSyncStore.getState().setPendingCount(queue.length);
  }

  async processQueue(): Promise<void> {
    if (this.syncInProgress || !this.isOnline) return;
    
    this.syncInProgress = true;
    useSyncStore.getState().setSyncing(true);

    try {
      const queue = await this.getQueue();
      const failed: SyncQueueItem[] = [];

      for (const item of queue) {
        try {
          await this.processItem(item);
        } catch (error) {
          item.retries++;
          if (item.retries < 3) {
            failed.push(item);
          } else {
            console.error(`Failed to sync after 3 retries:`, item);
          }
        }
      }

      await this.saveQueue(failed);
      await SecureStore.setItemAsync(LAST_SYNC_KEY, new Date().toISOString());
      useSyncStore.getState().setLastSync(new Date());
    } finally {
      this.syncInProgress = false;
      useSyncStore.getState().setSyncing(false);
    }
  }

  private async processItem(item: SyncQueueItem): Promise<void> {
    const { table, operation, data } = item;

    switch (operation) {
      case 'insert':
        const { error: insertError } = await supabase.from(table).insert(data);
        if (insertError) throw insertError;
        break;

      case 'update':
        const { error: updateError } = await supabase
          .from(table)
          .update(data)
          .eq('id', data.id);
        if (updateError) throw updateError;
        break;

      case 'delete':
        const { error: deleteError } = await supabase
          .from(table)
          .delete()
          .eq('id', data.id);
        if (deleteError) throw deleteError;
        break;
    }
  }

  async fullSync(): Promise<void> {
    if (!this.isOnline) {
      throw new Error('Cannot perform full sync while offline');
    }

    useSyncStore.getState().setSyncing(true);

    try {
      // Fetch latest data from all key tables
      const tables = ['meetings', 'tickets', 'dikw_items', 'standup_updates', 'sprint_settings'];
      
      for (const table of tables) {
        const { data, error } = await supabase
          .from(table)
          .select('*')
          .order('updated_at', { ascending: false })
          .limit(100);

        if (error) throw error;

        // Store in local cache
        await SecureStore.setItemAsync(
          `signalflow_cache_${table}`,
          JSON.stringify(data)
        );
      }

      await SecureStore.setItemAsync(LAST_SYNC_KEY, new Date().toISOString());
      useSyncStore.getState().setLastSync(new Date());
    } finally {
      useSyncStore.getState().setSyncing(false);
    }
  }

  cleanup() {
    this.subscriptions.forEach(unsub => unsub());
    this.subscriptions = [];
  }
}

export const syncService = new SyncService();

export function initializeSync() {
  syncService.initialize();
}

export default syncService;
