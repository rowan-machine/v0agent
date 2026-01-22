import React from 'react';
import { View, Text, StyleSheet, FlatList, TouchableOpacity } from 'react-native';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import api from '../services/api';

const STATUS_COLORS: Record<string, string> = {
  backlog: '#6b7280',
  todo: '#3b82f6',
  in_progress: '#f59e0b',
  in_review: '#8b5cf6',
  blocked: '#ef4444',
  done: '#22c55e',
};

const STATUS_LABELS: Record<string, string> = {
  backlog: 'Backlog',
  todo: 'To Do',
  in_progress: 'In Progress',
  in_review: 'In Review',
  blocked: 'Blocked',
  done: 'Done',
};

export default function TicketsScreen() {
  const queryClient = useQueryClient();
  
  const { data: tickets, isLoading, refetch } = useQuery({
    queryKey: ['tickets', 'sprint'],
    queryFn: () => api.tickets.list(true),
  });

  const updateStatus = useMutation({
    mutationFn: ({ id, status }: { id: string; status: string }) =>
      api.tickets.updateStatus(id, status),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['tickets'] });
    },
  });

  const groupedTickets = React.useMemo(() => {
    if (!tickets) return {};
    
    return tickets.reduce((acc, ticket) => {
      const status = ticket.status || 'backlog';
      if (!acc[status]) acc[status] = [];
      acc[status].push(ticket);
      return acc;
    }, {} as Record<string, typeof tickets>);
  }, [tickets]);

  const renderTicket = ({ item }: { item: any }) => (
    <TouchableOpacity style={styles.ticketCard}>
      <View style={styles.ticketHeader}>
        <Text style={styles.ticketId}>{item.ticket_id}</Text>
        <View style={[styles.statusBadge, { backgroundColor: STATUS_COLORS[item.status] }]}>
          <Text style={styles.statusText}>{STATUS_LABELS[item.status]}</Text>
        </View>
      </View>
      <Text style={styles.ticketTitle}>{item.title}</Text>
      {item.sprint_points > 0 && (
        <Text style={styles.points}>{item.sprint_points} pts</Text>
      )}
    </TouchableOpacity>
  );

  const statusOrder = ['in_progress', 'todo', 'in_review', 'blocked', 'backlog', 'done'];

  return (
    <View style={styles.container}>
      <FlatList
        data={statusOrder.filter(s => groupedTickets[s]?.length > 0)}
        renderItem={({ item: status }) => (
          <View>
            <View style={styles.statusHeader}>
              <View style={[styles.statusDot, { backgroundColor: STATUS_COLORS[status] }]} />
              <Text style={styles.statusTitle}>
                {STATUS_LABELS[status]} ({groupedTickets[status]?.length || 0})
              </Text>
            </View>
            {groupedTickets[status]?.map(ticket => (
              <View key={ticket.id}>
                {renderTicket({ item: ticket })}
              </View>
            ))}
          </View>
        )}
        keyExtractor={item => item}
        contentContainerStyle={styles.listContent}
        refreshing={isLoading}
        onRefresh={refetch}
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
  statusHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 12,
    marginTop: 8,
  },
  statusDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    marginRight: 8,
  },
  statusTitle: {
    fontSize: 14,
    fontWeight: '600',
    color: '#fff',
  },
  ticketCard: {
    backgroundColor: '#1a1a2e',
    borderRadius: 10,
    padding: 14,
    marginBottom: 10,
    marginLeft: 16,
  },
  ticketHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 6,
  },
  ticketId: {
    fontSize: 11,
    color: '#4a90d9',
    fontWeight: '600',
  },
  statusBadge: {
    paddingHorizontal: 8,
    paddingVertical: 2,
    borderRadius: 10,
  },
  statusText: {
    fontSize: 10,
    color: '#fff',
    fontWeight: '500',
  },
  ticketTitle: {
    fontSize: 14,
    color: '#fff',
  },
  points: {
    fontSize: 11,
    color: '#888',
    marginTop: 6,
  },
});
