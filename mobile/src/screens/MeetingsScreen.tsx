import React from 'react';
import { View, Text, StyleSheet, FlatList, TouchableOpacity } from 'react-native';
import { useQuery } from '@tanstack/react-query';
import api from '../services/api';

export default function MeetingsScreen() {
  const { data: meetings, isLoading, refetch } = useQuery({
    queryKey: ['meetings'],
    queryFn: () => api.meetings.list(50),
  });

  const renderMeeting = ({ item }: { item: any }) => (
    <TouchableOpacity style={styles.meetingCard}>
      <View style={styles.meetingHeader}>
        <Text style={styles.meetingTitle}>{item.meeting_name}</Text>
        <Text style={styles.meetingDate}>
          {item.meeting_date ? new Date(item.meeting_date).toLocaleDateString() : ''}
        </Text>
      </View>
      
      {item.synthesized_notes && (
        <Text style={styles.meetingNotes} numberOfLines={3}>
          {item.synthesized_notes}
        </Text>
      )}
      
      {item.signals && (
        <View style={styles.signalsRow}>
          {item.signals.decisions?.length > 0 && (
            <View style={styles.signalBadge}>
              <Text style={styles.signalText}>✅ {item.signals.decisions.length}</Text>
            </View>
          )}
          {item.signals.action_items?.length > 0 && (
            <View style={[styles.signalBadge, { backgroundColor: '#3b82f6' }]}>
              <Text style={styles.signalText}>📋 {item.signals.action_items.length}</Text>
            </View>
          )}
          {item.signals.blockers?.length > 0 && (
            <View style={[styles.signalBadge, { backgroundColor: '#ef4444' }]}>
              <Text style={styles.signalText}>🚧 {item.signals.blockers.length}</Text>
            </View>
          )}
        </View>
      )}
    </TouchableOpacity>
  );

  return (
    <View style={styles.container}>
      <FlatList
        data={meetings}
        renderItem={renderMeeting}
        keyExtractor={item => item.id}
        contentContainerStyle={styles.listContent}
        refreshing={isLoading}
        onRefresh={refetch}
        ListEmptyComponent={
          <View style={styles.emptyState}>
            <Text style={styles.emptyText}>No meetings yet</Text>
          </View>
        }
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#0f0f1a',
  },
  listContent: {
    padding: 15,
  },
  meetingCard: {
    backgroundColor: '#1a1a2e',
    borderRadius: 12,
    padding: 16,
    marginBottom: 12,
  },
  meetingHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    marginBottom: 8,
  },
  meetingTitle: {
    fontSize: 16,
    fontWeight: '600',
    color: '#fff',
    flex: 1,
  },
  meetingDate: {
    fontSize: 12,
    color: '#888',
    marginLeft: 10,
  },
  meetingNotes: {
    fontSize: 13,
    color: '#aaa',
    lineHeight: 18,
  },
  signalsRow: {
    flexDirection: 'row',
    marginTop: 12,
    gap: 8,
  },
  signalBadge: {
    backgroundColor: '#22c55e',
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 12,
  },
  signalText: {
    fontSize: 11,
    color: '#fff',
  },
  emptyState: {
    alignItems: 'center',
    paddingVertical: 40,
  },
  emptyText: {
    color: '#888',
    fontSize: 14,
  },
});
