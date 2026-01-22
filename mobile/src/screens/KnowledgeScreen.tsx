import React, { useState } from 'react';
import { View, Text, StyleSheet, FlatList, TouchableOpacity } from 'react-native';
import { useQuery } from '@tanstack/react-query';
import api from '../services/api';

const LEVELS = ['data', 'information', 'knowledge', 'wisdom'] as const;

const LEVEL_COLORS: Record<string, string> = {
  data: '#6b7280',
  information: '#3b82f6',
  knowledge: '#8b5cf6',
  wisdom: '#f59e0b',
};

const LEVEL_ICONS: Record<string, string> = {
  data: '📊',
  information: '💡',
  knowledge: '🧠',
  wisdom: '✨',
};

export default function KnowledgeScreen() {
  const [selectedLevel, setSelectedLevel] = useState<string | null>(null);

  const { data: items, isLoading, refetch } = useQuery({
    queryKey: ['dikw', selectedLevel],
    queryFn: () => api.dikw.list(selectedLevel || undefined),
  });

  const renderItem = ({ item }: { item: any }) => (
    <TouchableOpacity style={styles.itemCard}>
      <View style={styles.itemHeader}>
        <View style={[styles.levelBadge, { backgroundColor: LEVEL_COLORS[item.level] }]}>
          <Text style={styles.levelIcon}>{LEVEL_ICONS[item.level]}</Text>
          <Text style={styles.levelText}>{item.level}</Text>
        </View>
        {item.confidence && (
          <Text style={styles.confidence}>
            {Math.round(item.confidence * 100)}% confidence
          </Text>
        )}
      </View>
      
      <Text style={styles.itemContent}>{item.content}</Text>
      
      {item.tags && item.tags.length > 0 && (
        <View style={styles.tagsRow}>
          {item.tags.slice(0, 3).map((tag: string, i: number) => (
            <View key={i} style={styles.tag}>
              <Text style={styles.tagText}>{tag}</Text>
            </View>
          ))}
        </View>
      )}
    </TouchableOpacity>
  );

  return (
    <View style={styles.container}>
      {/* Level Filter */}
      <View style={styles.filterRow}>
        <TouchableOpacity
          style={[styles.filterButton, !selectedLevel && styles.filterActive]}
          onPress={() => setSelectedLevel(null)}
        >
          <Text style={[styles.filterText, !selectedLevel && styles.filterTextActive]}>
            All
          </Text>
        </TouchableOpacity>
        {LEVELS.map(level => (
          <TouchableOpacity
            key={level}
            style={[
              styles.filterButton,
              selectedLevel === level && styles.filterActive,
              { borderColor: LEVEL_COLORS[level] }
            ]}
            onPress={() => setSelectedLevel(level)}
          >
            <Text style={[
              styles.filterText,
              selectedLevel === level && styles.filterTextActive
            ]}>
              {LEVEL_ICONS[level]}
            </Text>
          </TouchableOpacity>
        ))}
      </View>

      <FlatList
        data={items}
        renderItem={renderItem}
        keyExtractor={item => item.id}
        contentContainerStyle={styles.listContent}
        refreshing={isLoading}
        onRefresh={refetch}
        ListEmptyComponent={
          <View style={styles.emptyState}>
            <Text style={styles.emptyText}>No knowledge items yet</Text>
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
  filterRow: {
    flexDirection: 'row',
    padding: 15,
    gap: 8,
  },
  filterButton: {
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderRadius: 20,
    borderWidth: 1,
    borderColor: '#333',
  },
  filterActive: {
    backgroundColor: '#1a1a2e',
    borderColor: '#4a90d9',
  },
  filterText: {
    color: '#888',
    fontSize: 13,
  },
  filterTextActive: {
    color: '#fff',
  },
  listContent: {
    padding: 15,
    paddingTop: 0,
  },
  itemCard: {
    backgroundColor: '#1a1a2e',
    borderRadius: 12,
    padding: 16,
    marginBottom: 12,
  },
  itemHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 10,
  },
  levelBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 12,
    gap: 4,
  },
  levelIcon: {
    fontSize: 12,
  },
  levelText: {
    fontSize: 11,
    color: '#fff',
    textTransform: 'capitalize',
  },
  confidence: {
    fontSize: 11,
    color: '#888',
  },
  itemContent: {
    fontSize: 14,
    color: '#fff',
    lineHeight: 20,
  },
  tagsRow: {
    flexDirection: 'row',
    marginTop: 12,
    gap: 6,
  },
  tag: {
    backgroundColor: '#2a2a4e',
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 8,
  },
  tagText: {
    fontSize: 11,
    color: '#aaa',
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
