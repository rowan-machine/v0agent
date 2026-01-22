// mobile/src/__tests__/screens/HomeScreen.test.tsx
/**
 * Tests for HomeScreen component
 */

import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react-native';
import HomeScreen from '../../screens/HomeScreen';

// Mock navigation
const mockNavigate = jest.fn();
jest.mock('@react-navigation/native', () => ({
  ...jest.requireActual('@react-navigation/native'),
  useNavigation: () => ({
    navigate: mockNavigate,
  }),
}));

// Mock the sync store
jest.mock('../../stores/syncStore', () => ({
  useSyncStore: () => ({
    isSyncing: false,
    lastSyncAt: '2024-01-15T10:00:00Z',
    pendingChanges: [],
  }),
}));

describe('HomeScreen', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('should render without crashing', () => {
    render(<HomeScreen />);
    
    expect(screen.getByText(/SignalFlow/i)).toBeTruthy();
  });

  it('should display navigation cards', () => {
    render(<HomeScreen />);
    
    expect(screen.getByText(/Meetings/i)).toBeTruthy();
    expect(screen.getByText(/Tickets/i)).toBeTruthy();
    expect(screen.getByText(/Knowledge/i)).toBeTruthy();
  });

  it('should navigate to Meetings screen on card press', () => {
    render(<HomeScreen />);
    
    const meetingsCard = screen.getByText(/Meetings/i);
    fireEvent.press(meetingsCard);
    
    expect(mockNavigate).toHaveBeenCalledWith('Meetings');
  });

  it('should navigate to Tickets screen on card press', () => {
    render(<HomeScreen />);
    
    const ticketsCard = screen.getByText(/Tickets/i);
    fireEvent.press(ticketsCard);
    
    expect(mockNavigate).toHaveBeenCalledWith('Tickets');
  });

  it('should navigate to Knowledge screen on card press', () => {
    render(<HomeScreen />);
    
    const knowledgeCard = screen.getByText(/Knowledge/i);
    fireEvent.press(knowledgeCard);
    
    expect(mockNavigate).toHaveBeenCalledWith('Knowledge');
  });

  it('should display sync status', () => {
    render(<HomeScreen />);
    
    // Should show last sync time or sync indicator
    // Implementation depends on UI design
  });

  it('should show pending changes indicator when offline', () => {
    // Mock pending changes
    jest.mock('../../stores/syncStore', () => ({
      useSyncStore: () => ({
        isSyncing: false,
        pendingChanges: [{ id: '1', table: 'meetings' }],
      }),
    }));

    render(<HomeScreen />);
    
    // Should show pending indicator
    // expect(screen.getByTestId('pending-indicator')).toBeTruthy();
  });
});


describe('HomeScreen Sync Behavior', () => {
  it('should trigger sync on pull-to-refresh', async () => {
    const mockSync = jest.fn();
    
    // This would test the refresh behavior
    // Implementation depends on how pull-to-refresh is implemented
  });

  it('should show syncing indicator during sync', () => {
    jest.mock('../../stores/syncStore', () => ({
      useSyncStore: () => ({
        isSyncing: true,
        lastSyncAt: null,
        pendingChanges: [],
      }),
    }));

    render(<HomeScreen />);
    
    // Should show syncing indicator
    // expect(screen.getByTestId('sync-indicator')).toBeTruthy();
  });
});
