import React from 'react';
import { View, Text, StyleSheet, ScrollView, TouchableOpacity, Switch } from 'react-native';
import { useAuthStore } from '../stores/authStore';
import { useSyncStore } from '../stores/syncStore';
import syncService from '../services/sync';

export default function SettingsScreen() {
  const { user, signOut } = useAuthStore();
  const { isSyncing, lastSync, pendingCount } = useSyncStore();

  const handleManualSync = async () => {
    try {
      await syncService.fullSync();
    } catch (error) {
      console.error('Sync failed:', error);
    }
  };

  return (
    <ScrollView style={styles.container}>
      {/* User Section */}
      <View style={styles.section}>
        <Text style={styles.sectionTitle}>Account</Text>
        <View style={styles.card}>
          <Text style={styles.label}>Email</Text>
          <Text style={styles.value}>{user?.email || 'Not signed in'}</Text>
        </View>
      </View>

      {/* Sync Section */}
      <View style={styles.section}>
        <Text style={styles.sectionTitle}>Sync</Text>
        <View style={styles.card}>
          <View style={styles.row}>
            <Text style={styles.label}>Status</Text>
            <Text style={[styles.value, { color: isSyncing ? '#4a90d9' : '#22c55e' }]}>
              {isSyncing ? 'Syncing...' : 'Up to date'}
            </Text>
          </View>
          <View style={styles.row}>
            <Text style={styles.label}>Last Sync</Text>
            <Text style={styles.value}>
              {lastSync ? lastSync.toLocaleString() : 'Never'}
            </Text>
          </View>
          <View style={styles.row}>
            <Text style={styles.label}>Pending Changes</Text>
            <Text style={styles.value}>{pendingCount}</Text>
          </View>
        </View>
        
        <TouchableOpacity 
          style={styles.button}
          onPress={handleManualSync}
          disabled={isSyncing}
        >
          <Text style={styles.buttonText}>
            {isSyncing ? 'Syncing...' : 'Sync Now'}
          </Text>
        </TouchableOpacity>
      </View>

      {/* Preferences Section */}
      <View style={styles.section}>
        <Text style={styles.sectionTitle}>Preferences</Text>
        <View style={styles.card}>
          <View style={styles.row}>
            <Text style={styles.label}>Push Notifications</Text>
            <Switch
              value={true}
              trackColor={{ false: '#333', true: '#4a90d9' }}
              thumbColor="#fff"
            />
          </View>
          <View style={styles.row}>
            <Text style={styles.label}>Dark Mode</Text>
            <Switch
              value={true}
              trackColor={{ false: '#333', true: '#4a90d9' }}
              thumbColor="#fff"
              disabled
            />
          </View>
        </View>
      </View>

      {/* About Section */}
      <View style={styles.section}>
        <Text style={styles.sectionTitle}>About</Text>
        <View style={styles.card}>
          <View style={styles.row}>
            <Text style={styles.label}>Version</Text>
            <Text style={styles.value}>1.0.0</Text>
          </View>
          <View style={styles.row}>
            <Text style={styles.label}>Build</Text>
            <Text style={styles.value}>2026.01.22</Text>
          </View>
        </View>
      </View>

      {/* Sign Out */}
      <TouchableOpacity 
        style={[styles.button, styles.dangerButton]}
        onPress={signOut}
      >
        <Text style={[styles.buttonText, styles.dangerText]}>Sign Out</Text>
      </TouchableOpacity>

      <View style={styles.footer} />
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#0f0f1a',
  },
  section: {
    padding: 15,
  },
  sectionTitle: {
    fontSize: 13,
    fontWeight: '600',
    color: '#888',
    textTransform: 'uppercase',
    marginBottom: 10,
  },
  card: {
    backgroundColor: '#1a1a2e',
    borderRadius: 12,
    padding: 4,
  },
  row: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: 14,
    borderBottomWidth: 1,
    borderBottomColor: '#2a2a4e',
  },
  label: {
    fontSize: 14,
    color: '#fff',
  },
  value: {
    fontSize: 14,
    color: '#888',
  },
  button: {
    backgroundColor: '#4a90d9',
    borderRadius: 10,
    padding: 14,
    alignItems: 'center',
    marginTop: 10,
  },
  buttonText: {
    color: '#fff',
    fontSize: 14,
    fontWeight: '600',
  },
  dangerButton: {
    backgroundColor: 'transparent',
    borderWidth: 1,
    borderColor: '#ef4444',
    marginHorizontal: 15,
    marginTop: 20,
  },
  dangerText: {
    color: '#ef4444',
  },
  footer: {
    height: 40,
  },
});
