import React from 'react';
import { View, Text, StyleSheet, ScrollView, TouchableOpacity } from 'react-native';
import { useQuery } from '@tanstack/react-query';
import api from '../services/api';
import { useSyncStore } from '../stores/syncStore';

export default function HomeScreen() {
  const { isSyncing, lastSync, pendingCount } = useSyncStore();

  const { data: meetings } = useQuery({
    queryKey: ['meetings', 'recent'],
    queryFn: () => api.meetings.list(5),
  });

  const { data: tickets } = useQuery({
    queryKey: ['tickets', 'sprint'],
    queryFn: () => api.tickets.list(true),
  });

  const inProgressCount = tickets?.filter(t => t.status === 'in_progress').length || 0;
  const todoCount = tickets?.filter(t => t.status === 'todo').length || 0;

  return (
    <ScrollView style={styles.container}>
      {/* Sync Status Banner */}
      {pendingCount > 0 && (
        <View style={styles.syncBanner}>
          <Text style={styles.syncText}>
            {isSyncing ? 'Syncing...' : `${pendingCount} pending changes`}
          </Text>
        </View>
      )}

      {/* Dashboard Header */}
      <View style={styles.header}>
        <Text style={styles.title}>SignalFlow</Text>
        <Text style={styles.subtitle}>
          {lastSync ? `Last sync: ${lastSync.toLocaleTimeString()}` : 'Not synced yet'}
        </Text>
      </View>

      {/* Quick Stats */}
      <View style={styles.statsRow}>
        <View style={styles.statCard}>
          <Text style={styles.statNumber}>{inProgressCount}</Text>
          <Text style={styles.statLabel}>In Progress</Text>
        </View>
        <View style={styles.statCard}>
          <Text style={styles.statNumber}>{todoCount}</Text>
          <Text style={styles.statLabel}>To Do</Text>
        </View>
        <View style={styles.statCard}>
          <Text style={styles.statNumber}>{meetings?.length || 0}</Text>
          <Text style={styles.statLabel}>Recent Meetings</Text>
        </View>
      </View>

      {/* Quick Actions */}
      <Text style={styles.sectionTitle}>Quick Actions</Text>
      <View style={styles.actionsRow}>
        <TouchableOpacity style={styles.actionButton}>
          <Text style={styles.actionIcon}>📝</Text>
          <Text style={styles.actionLabel}>Standup</Text>
        </TouchableOpacity>
        <TouchableOpacity style={styles.actionButton}>
          <Text style={styles.actionIcon}>🎯</Text>
          <Text style={styles.actionLabel}>Quick Ask</Text>
        </TouchableOpacity>
        <TouchableOpacity style={styles.actionButton}>
          <Text style={styles.actionIcon}>🔍</Text>
          <Text style={styles.actionLabel}>Search</Text>
        </TouchableOpacity>
      </View>

      {/* Recent Meetings */}
      <Text style={styles.sectionTitle}>Recent Meetings</Text>
      {meetings?.map(meeting => (
        <TouchableOpacity key={meeting.id} style={styles.listItem}>
          <Text style={styles.listItemTitle}>{meeting.meeting_name}</Text>
          <Text style={styles.listItemSubtitle}>
            {meeting.meeting_date ? new Date(meeting.meeting_date).toLocaleDateString() : 'No date'}
          </Text>
        </TouchableOpacity>
      ))}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#0f0f1a',
  },
  syncBanner: {
    backgroundColor: '#4a90d9',
    padding: 8,
    alignItems: 'center',
  },
  syncText: {
    color: '#fff',
    fontSize: 12,
  },
  header: {
    padding: 20,
    paddingTop: 10,
  },
  title: {
    fontSize: 28,
    fontWeight: 'bold',
    color: '#fff',
  },
  subtitle: {
    fontSize: 12,
    color: '#888',
    marginTop: 4,
  },
  statsRow: {
    flexDirection: 'row',
    paddingHorizontal: 10,
    marginBottom: 20,
  },
  statCard: {
    flex: 1,
    backgroundColor: '#1a1a2e',
    borderRadius: 12,
    padding: 16,
    marginHorizontal: 5,
    alignItems: 'center',
  },
  statNumber: {
    fontSize: 24,
    fontWeight: 'bold',
    color: '#4a90d9',
  },
  statLabel: {
    fontSize: 12,
    color: '#888',
    marginTop: 4,
  },
  sectionTitle: {
    fontSize: 16,
    fontWeight: '600',
    color: '#fff',
    paddingHorizontal: 20,
    paddingVertical: 10,
  },
  actionsRow: {
    flexDirection: 'row',
    paddingHorizontal: 10,
    marginBottom: 20,
  },
  actionButton: {
    flex: 1,
    backgroundColor: '#1a1a2e',
    borderRadius: 12,
    padding: 16,
    marginHorizontal: 5,
    alignItems: 'center',
  },
  actionIcon: {
    fontSize: 24,
  },
  actionLabel: {
    fontSize: 12,
    color: '#fff',
    marginTop: 8,
  },
  listItem: {
    backgroundColor: '#1a1a2e',
    marginHorizontal: 15,
    marginBottom: 10,
    borderRadius: 8,
    padding: 16,
  },
  listItemTitle: {
    fontSize: 14,
    fontWeight: '600',
    color: '#fff',
  },
  listItemSubtitle: {
    fontSize: 12,
    color: '#888',
    marginTop: 4,
  },
});
