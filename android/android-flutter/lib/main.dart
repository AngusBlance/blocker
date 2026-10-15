import 'package:flutter/material.dart';

import 'backend.dart';
import 'blocker.dart';
import 'screens/home.dart';
import 'screens/schedules_screen.dart';
import 'screens/settings.dart';
import 'screens/sites.dart';
import 'screens/unlock.dart';
import 'sites.dart';
import 'theme.dart';

void main() {
  runApp(BlockerApp(backend: ChannelBackend()));
}

enum Tab { home, sites, schedules, settings }

// Labels match the TUI's sidebar sections.
const _tabs = [
  (tab: Tab.home, label: 'dashboard', icon: Icons.dashboard_outlined),
  (tab: Tab.sites, label: 'sites', icon: Icons.public_off),
  (tab: Tab.schedules, label: 'schedules', icon: Icons.schedule_outlined),
  (tab: Tab.settings, label: 'settings', icon: Icons.settings_outlined),
];

class BlockerApp extends StatefulWidget {
  const BlockerApp({super.key, required this.backend, this.clock});

  final Backend backend;

  /// The current time; swapped for a fixed clock in tests.
  final DateTime Function()? clock;

  @override
  State<BlockerApp> createState() => _BlockerAppState();
}

class _BlockerAppState extends State<BlockerApp> {
  late final Blocker blocker = Blocker(widget.backend, clock: widget.clock)
    ..load();
  Tab tab = Tab.home;

  void go(Tab next) => setState(() => tab = next);

  /// Unlocking is its own screen over the tabs, opened from sites.
  void _unlock(BuildContext context, Site? site) => Navigator.of(context).push(
    MaterialPageRoute<void>(
      builder: (route) => Scaffold(
        body: SafeArea(
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(12),
            child: UnlockScreen(
              blocker: blocker,
              site: site,
              done: () => Navigator.of(route).pop(),
            ),
          ),
        ),
      ),
    ),
  );

  @override
  void dispose() {
    blocker.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Blocker',
      debugShowCheckedModeBanner: false,
      theme: buildTheme(),
      home: ListenableBuilder(
        listenable: blocker,
        builder: (context, _) => Scaffold(
          body: SafeArea(
            child: Column(
              children: [
                Container(
                  width: double.infinity,
                  color: AppColors.panel,
                  padding: const EdgeInsets.symmetric(vertical: 10),
                  alignment: Alignment.center,
                  child: Text('blocker', style: monoStyle()),
                ),
                Expanded(
                  child: blocker.loaded
                      ? SingleChildScrollView(
                          padding: const EdgeInsets.all(12),
                          child: _screen(context),
                        )
                      : const SizedBox.shrink(),
                ),
                _TabBar(current: tab, onSelect: go),
              ],
            ),
          ),
        ),
      ),
    );
  }

  Widget _screen(BuildContext context) {
    switch (tab) {
      case Tab.home:
        return HomeScreen(blocker: blocker, goToSites: () => go(Tab.sites));
      case Tab.sites:
        return SitesScreen(
          blocker: blocker,
          requestUnlock: (site) => _unlock(context, site),
        );
      case Tab.schedules:
        return SchedulesScreen(blocker: blocker);
      case Tab.settings:
        return SettingsScreen(blocker: blocker);
    }
  }
}

/// Four square tiles; the active one gets the accent border.
class _TabBar extends StatelessWidget {
  const _TabBar({required this.current, required this.onSelect});

  final Tab current;
  final void Function(Tab) onSelect;

  @override
  Widget build(BuildContext context) {
    return Container(
      color: AppColors.surface,
      padding: const EdgeInsets.all(8),
      child: Row(
        children: [
          for (final (i, t) in _tabs.indexed) ...[
            if (i > 0) const SizedBox(width: 8),
            Expanded(
              child: AspectRatio(
                aspectRatio: 1,
                child: ConstrainedBox(
                  constraints: const BoxConstraints(maxHeight: 84),
                  child: Material(
                    color: AppColors.background,
                    shape: RoundedRectangleBorder(
                      side: BorderSide(
                        color: current == t.tab
                            ? AppColors.accent
                            : AppColors.border,
                      ),
                    ),
                    child: InkWell(
                      key: Key('tab-${t.label}'),
                      onTap: () => onSelect(t.tab),
                      child: Column(
                        mainAxisAlignment: MainAxisAlignment.center,
                        children: [
                          Icon(
                            t.icon,
                            size: 26,
                            color: current == t.tab
                                ? AppColors.accent
                                : AppColors.muted,
                          ),
                          const SizedBox(height: 4),
                          Text(
                            t.label,
                            style: monoStyle(
                              size: 11,
                              color: current == t.tab
                                  ? AppColors.accent
                                  : AppColors.muted,
                            ),
                          ),
                        ],
                      ),
                    ),
                  ),
                ),
              ),
            ),
          ],
        ],
      ),
    );
  }
}
