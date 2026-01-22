import { createClient } from '@supabase/supabase-js';
import * as SecureStore from 'expo-secure-store';
import { Database } from '../types/supabase';

// Environment configuration
const SUPABASE_URL = process.env.EXPO_PUBLIC_SUPABASE_URL || '';
const SUPABASE_ANON_KEY = process.env.EXPO_PUBLIC_SUPABASE_ANON_KEY || '';

// Create Supabase client with secure storage for auth tokens
export const supabase = createClient<Database>(SUPABASE_URL, SUPABASE_ANON_KEY, {
  auth: {
    storage: {
      async getItem(key: string) {
        return SecureStore.getItemAsync(key);
      },
      async setItem(key: string, value: string) {
        await SecureStore.setItemAsync(key, value);
      },
      async removeItem(key: string) {
        await SecureStore.deleteItemAsync(key);
      },
    },
    autoRefreshToken: true,
    persistSession: true,
    detectSessionInUrl: false,
  },
});

// API helpers for common operations
export const api = {
  // Meetings
  meetings: {
    async list(limit = 20) {
      const { data, error } = await supabase
        .from('meetings')
        .select('*')
        .order('meeting_date', { ascending: false })
        .limit(limit);
      if (error) throw error;
      return data;
    },
    async get(id: string) {
      const { data, error } = await supabase
        .from('meetings')
        .select('*')
        .eq('id', id)
        .single();
      if (error) throw error;
      return data;
    },
    async create(meeting: Partial<Database['public']['Tables']['meetings']['Insert']>) {
      const { data, error } = await supabase
        .from('meetings')
        .insert(meeting)
        .select()
        .single();
      if (error) throw error;
      return data;
    },
  },

  // Tickets
  tickets: {
    async list(inSprint = true) {
      let query = supabase
        .from('tickets')
        .select('*')
        .order('created_at', { ascending: false });
      
      if (inSprint) {
        query = query.eq('in_sprint', true);
      }
      
      const { data, error } = await query;
      if (error) throw error;
      return data;
    },
    async updateStatus(id: string, status: string) {
      const { data, error } = await supabase
        .from('tickets')
        .update({ status, updated_at: new Date().toISOString() })
        .eq('id', id)
        .select()
        .single();
      if (error) throw error;
      return data;
    },
  },

  // DIKW Items
  dikw: {
    async list(level?: string) {
      let query = supabase
        .from('dikw_items')
        .select('*')
        .eq('status', 'active')
        .order('created_at', { ascending: false });
      
      if (level) {
        query = query.eq('level', level);
      }
      
      const { data, error } = await query;
      if (error) throw error;
      return data;
    },
  },

  // Standup
  standup: {
    async submit(content: string) {
      const { data, error } = await supabase
        .from('standup_updates')
        .insert({
          content,
          sprint_date: new Date().toISOString().split('T')[0],
        })
        .select()
        .single();
      if (error) throw error;
      return data;
    },
    async getRecent(days = 7) {
      const since = new Date();
      since.setDate(since.getDate() - days);
      
      const { data, error } = await supabase
        .from('standup_updates')
        .select('*')
        .gte('sprint_date', since.toISOString().split('T')[0])
        .order('sprint_date', { ascending: false });
      if (error) throw error;
      return data;
    },
  },

  // Search
  search: {
    async semantic(query: string, types?: string[]) {
      // Call the semantic search edge function
      const { data, error } = await supabase.functions.invoke('semantic-search', {
        body: { query, types, limit: 10 },
      });
      if (error) throw error;
      return data;
    },
  },
};

export default api;
