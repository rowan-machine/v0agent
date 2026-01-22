// mobile/src/__tests__/services/api.test.ts
/**
 * Tests for Supabase API service
 */

import { supabase, isOnline, getMeetings, getDocuments, getTickets } from '../../services/api';

// Mock the supabase client
jest.mock('../../services/api', () => {
  const originalModule = jest.requireActual('../../services/api');
  return {
    ...originalModule,
    supabase: {
      auth: {
        getSession: jest.fn().mockResolvedValue({ data: { session: null }, error: null }),
      },
      from: jest.fn(() => ({
        select: jest.fn().mockReturnThis(),
        insert: jest.fn().mockReturnThis(),
        update: jest.fn().mockReturnThis(),
        delete: jest.fn().mockReturnThis(),
        eq: jest.fn().mockReturnThis(),
        order: jest.fn().mockReturnThis(),
        limit: jest.fn().mockReturnThis(),
        single: jest.fn().mockResolvedValue({ data: null, error: null }),
      })),
    },
  };
});

describe('API Service', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe('isOnline', () => {
    it('should return network connectivity status', async () => {
      const result = await isOnline();
      expect(typeof result).toBe('boolean');
    });
  });

  describe('getMeetings', () => {
    it('should fetch meetings from Supabase', async () => {
      const mockMeetings = [
        { id: '1', meeting_name: 'Test Meeting', synthesized_notes: 'Notes' },
      ];

      (supabase.from as jest.Mock).mockReturnValue({
        select: jest.fn().mockReturnThis(),
        order: jest.fn().mockReturnThis(),
        limit: jest.fn().mockResolvedValue({ data: mockMeetings, error: null }),
      });

      const meetings = await getMeetings();
      
      expect(supabase.from).toHaveBeenCalledWith('meetings');
    });

    it('should handle errors gracefully', async () => {
      (supabase.from as jest.Mock).mockReturnValue({
        select: jest.fn().mockReturnThis(),
        order: jest.fn().mockReturnThis(),
        limit: jest.fn().mockResolvedValue({ 
          data: null, 
          error: { message: 'Network error' } 
        }),
      });

      await expect(getMeetings()).rejects.toThrow();
    });
  });

  describe('getDocuments', () => {
    it('should fetch documents from Supabase', async () => {
      const mockDocs = [
        { id: '1', source: 'Test Doc', content: 'Content' },
      ];

      (supabase.from as jest.Mock).mockReturnValue({
        select: jest.fn().mockReturnThis(),
        order: jest.fn().mockReturnThis(),
        limit: jest.fn().mockResolvedValue({ data: mockDocs, error: null }),
      });

      const docs = await getDocuments();
      
      expect(supabase.from).toHaveBeenCalledWith('documents');
    });
  });

  describe('getTickets', () => {
    it('should fetch tickets from Supabase', async () => {
      const mockTickets = [
        { id: '1', ticket_id: 'TEST-001', title: 'Test Ticket' },
      ];

      (supabase.from as jest.Mock).mockReturnValue({
        select: jest.fn().mockReturnThis(),
        order: jest.fn().mockReturnThis(),
        limit: jest.fn().mockResolvedValue({ data: mockTickets, error: null }),
      });

      const tickets = await getTickets();
      
      expect(supabase.from).toHaveBeenCalledWith('tickets');
    });
  });
});
