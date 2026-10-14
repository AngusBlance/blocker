import MaterialCommunityIcons from '@expo/vector-icons/MaterialCommunityIcons';
import { StatusBar } from 'expo-status-bar';
import { ComponentProps, useState } from 'react';
import { Pressable, ScrollView, StyleSheet, View } from 'react-native';
import { SafeAreaProvider, SafeAreaView } from 'react-native-safe-area-context';

import { HomeScreen } from './src/screens/HomeScreen';
import { SettingsScreen } from './src/screens/SettingsScreen';
import { SitesScreen } from './src/screens/SitesScreen';
import { UnlockScreen } from './src/screens/UnlockScreen';
import type { Site } from './src/sites';
import { colors } from './src/theme';
import { Mono } from './src/ui';
import { useBlocker } from './src/useBlocker';

export type Tab = 'home' | 'sites' | 'unlock' | 'settings';

type IconName = ComponentProps<typeof MaterialCommunityIcons>['name'];

// Labels match the TUI's sidebar sections.
const TABS: { key: Tab; label: string; icon: IconName }[] = [
  { key: 'home', label: 'dashboard', icon: 'view-dashboard-outline' },
  { key: 'sites', label: 'sites', icon: 'web-cancel' },
  { key: 'unlock', label: 'unlock', icon: 'lock-open-variant-outline' },
  { key: 'settings', label: 'settings', icon: 'cog-outline' },
];

export default function App() {
  const blocker = useBlocker();
  const [tab, setTab] = useState<Tab>('home');
  const [pendingSite, setPendingSite] = useState<Site | null>(null);

  const go = (next: Tab) => {
    setPendingSite(null);
    setTab(next);
  };

  let screen;
  if (tab === 'home') screen = <HomeScreen blocker={blocker} go={go} />;
  else if (tab === 'sites')
    screen = (
      <SitesScreen
        blocker={blocker}
        requestUnlock={(site) => {
          setPendingSite(site);
          setTab('unlock');
        }}
      />
    );
  else if (tab === 'unlock')
    screen = (
      <UnlockScreen
        key={pendingSite?.name ?? 'all'}
        blocker={blocker}
        site={pendingSite}
        done={() => go(pendingSite ? 'sites' : 'home')}
      />
    );
  else screen = <SettingsScreen blocker={blocker} />;

  return (
    <SafeAreaProvider>
      <SafeAreaView style={styles.root} edges={['top', 'bottom']}>
        <StatusBar style="light" />
        <View style={styles.header}>
          <Mono style={styles.headerTitle}>blocker</Mono>
        </View>
        <ScrollView contentContainerStyle={styles.screen} keyboardShouldPersistTaps="handled">
          {screen}
        </ScrollView>
        <View style={styles.tabs}>
          {TABS.map((t) => {
            const active = tab === t.key;
            return (
              <Pressable
                key={t.key}
                onPress={() => go(t.key)}
                style={({ pressed }) => [
                  styles.tab,
                  active && styles.tabActive,
                  pressed && styles.tabPressed,
                ]}>
                <MaterialCommunityIcons
                  name={t.icon}
                  size={26}
                  color={active ? colors.accent : colors.muted}
                />
                <Mono style={[styles.tabLabel, active && styles.tabLabelActive]}>{t.label}</Mono>
              </Pressable>
            );
          })}
        </View>
      </SafeAreaView>
    </SafeAreaProvider>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.background },
  header: {
    backgroundColor: colors.panel,
    paddingVertical: 10,
    alignItems: 'center',
  },
  headerTitle: { color: colors.foreground },
  screen: { padding: 12, gap: 12 },
  tabs: { flexDirection: 'row', gap: 8, padding: 8, backgroundColor: colors.surface },
  tab: {
    flex: 1,
    aspectRatio: 1,
    maxHeight: 84,
    alignItems: 'center',
    justifyContent: 'center',
    gap: 4,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.background,
  },
  tabActive: { borderColor: colors.accent },
  tabPressed: { backgroundColor: colors.panel },
  tabLabel: { fontSize: 11, color: colors.muted },
  tabLabelActive: { color: colors.accent },
});
