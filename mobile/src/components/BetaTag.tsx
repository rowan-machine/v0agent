import React from 'react';
import { View, Text, StyleSheet, ViewStyle } from 'react-native';
import { FeatureStatus } from '../services/api';

interface BetaTagProps {
  status: FeatureStatus;
  style?: ViewStyle;
}

/**
 * Visual tag for feature stability status.
 * Shows BETA, ALPHA, etc. with appropriate colors.
 */
export default function BetaTag({ status, style }: BetaTagProps) {
  if (status === 'stable') {
    return null; // Don't show tag for stable features
  }

  const tagConfig = {
    beta: {
      label: 'BETA',
      backgroundColor: '#4a90d9',
      textColor: '#fff',
    },
    alpha: {
      label: 'ALPHA',
      backgroundColor: '#f59e0b',
      textColor: '#fff',
    },
    deprecated: {
      label: 'LEGACY',
      backgroundColor: '#6b7280',
      textColor: '#fff',
    },
    disabled: {
      label: 'OFF',
      backgroundColor: '#374151',
      textColor: '#9ca3af',
    },
  };

  const config = tagConfig[status];
  if (!config) return null;

  return (
    <View style={[styles.tag, { backgroundColor: config.backgroundColor }, style]}>
      <Text style={[styles.text, { color: config.textColor }]}>{config.label}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  tag: {
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderRadius: 4,
    marginLeft: 8,
  },
  text: {
    fontSize: 10,
    fontWeight: '700',
    letterSpacing: 0.5,
  },
});
