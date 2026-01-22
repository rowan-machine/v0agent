/**
 * Online-First Sync Service
 * 
 * Implements an online-first sync strategy with offline fallback:
 * 1. All writes go DIRECTLY to Supabase when online
 * 2. If offline, queue locally for later sync
 * 3. Background sync pushes queued changes when connection restored
 * 4. Real-time subscriptions for instant updates when online
 * 
 * This ensures data is always saved to Supabase when you have connectivity.
 */

import { supabase } from './api';
import * as SecureStore from 'expo-secure-store';
import NetInfo from '@react-native-community/netinfo';
import { useSyncStore } from '../stores/syncStore';

// Sync queue stored locally (only used when offline)
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
  private isOnline = true; // Default to online - assume connectivity
  private syncInProgress = false;
  private subscriptions: (() => void)[] = [];

  async initialize() {
    // Monitor network status
    NetInfo.addEventListener(state => {
      const wasOffline = !this.isOnline;
      this.isOnline = state.isConnected ?? true; // Default to true
      
      // Trigger sync when coming back online
      if (wasOffline && this.isOnline) {
        this.processQueue();
      }
      
      // Update store with connection status
      useSyncStore.getState().setOnline(this.isOnline);
    });

    // Initial network check
    const state = await NetInfo.fetch();
    this.isOnline = state.isConnected ?? true;
    useSyncStore.getState().setOnline(this.isOnline);

    // Set up real-time subscriptions
    this.setupRealtimeSubscriptions();

    // Process any pending queue items from previous offline session
    if (this.isOnline) {
      this.processQueue();
    }
  }

  /**
   * ONLINE-FIRST: Write directly to Supabase, fall back to queue if offline
   */
  async writeToSupabase(
    table: string,
    operation: 'insert' | 'update' | 'delete',
    data: Record<string, any>
  ): Promise<{ success: boolean; data?: any; queued?: boolean }> {
    // Try direct write to Supabase first (online-first)
    if (this.isOnline) {
      try {
        const result = await this.executeOperation(table, operation, data);
        return { success: true, data: result };
      } catch (error) {
        console.warn(`Direct Supabase write failed, queueing for later:`, error);
        // Fall through to queue
      }
    }

    // Offline or failed: Queue for later sync
    await this.queueOperation(table, operation, data);
    return { success: true, queued: true };
  }

  /**
   * Execute operation directly on Supabase
   */
  private async executeOperation(
    table: string,
    operation: 'insert' | 'update' | 'delete',
    data: Record<string, any>
  ): Promise<any> {
    switch (operation) {
      case 'insert': {
        const { data: result, error } = await supabase
          .from(table)
          .insert(data)
          .select()
          .single();
        if (error) throw error;
        return result;
      }
      case 'update': {
        const { data: result, error } = await supabase
          .from(table)
          .update(data)
          .eq('id', data.id)
          .select()
          .single();
        if (error) throw error;
        return result;
      }
      case 'delete': {
        const { error } = await supabase
          .from(table)
          .delete()
          .eq('id', data.id);
        if (error) throw error;
        return { id: data.id, deleted: true };
      }
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

  /**
   * Queue operation for later sync (only called when offline)
   */
  private async queueOperation(
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

    // Add to offline queue
    const queue = await this.getQueue();
    queue.push(item);
    await this.saveQueue(queue);
    
    console.log(`[OFFLINE] Queued ${operation} on ${table} for later sync`);
  }

  private async getQueue(): Promise<SyncQueueItem[]> {
    const stored = await SecureStore.getItemAsync(SYNC_QUEUE_KEY);
    return stored ? JSON.parse(stored) : [];
  }

  private async saveQueue(queue: SyncQueueItem[]): Promise<void> {
    await SecureStore.setItemAsync(SYNC_QUEUE_KEY, JSON.stringify(queue));
    useSyncStore.getState().setPendingCount(queue.length);
  }

  /**
   * Process queued operations when back online
   */
  async processQueue(): Promise<void> {
    if (this.syncInProgress || !this.isOnline) return;
    
    const queue = await this.getQueue();
    if (queue.length === 0) return;
    
    console.log(`[SYNC] Processing ${queue.length} queued operations...`);
    
    this.syncInProgress = true;
    useSyncStore.getState().setSyncing(true);

    try {
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
