import 'dart:math';

import 'package:flutter/widgets.dart';

import 'backend.dart';
import 'schedule.dart';
import 'sites.dart';

/// App state over androidlib. State lives natively; this re-reads it after
/// each change and whenever the app comes back to the foreground (e.g.
/// returning from the Accessibility settings screen).
class Blocker extends ChangeNotifier with WidgetsBindingObserver {
  Blocker(this.backend, {DateTime Function()? clock})
    : now = clock ?? DateTime.now {
    WidgetsBinding.instance.addObserver(this);
  }

  final Backend backend;

  /// The current time; swapped for a fixed clock in tests.
  final DateTime Function() now;

  List<Schedule> schedules = [];
  List<RunningSchedule> running = [];

  List<String> domains = [];
  List<String> apps = [];
  bool serviceEnabled = false;
  int sdkInt = 0;
  bool loaded = false;

  /// Android 13+ locks accessibility for apps installed outside the Play
  /// Store ("restricted settings").
  bool get hasRestrictedSettings => sdkInt >= 33;

  bool isBlocked(Site site) =>
      site.domains.every(domains.contains) && site.apps.every(apps.contains);

  List<Site> get blockedSites => sites.where(isBlocked).toList();

  Future<void> load() async {
    sdkInt = await backend.sdkInt();
    await _blockMissingApps();
    await refresh();
  }

  /// Sites blocked before app blocking existed have their domains but not
  /// their apps; block the apps too so they stay fully blocked.
  Future<void> _blockMissingApps() async {
    final blocked = await backend.blockedDomains();
    final missing = sites
        .where((s) => s.domains.every(blocked.contains))
        .expand((s) => s.apps)
        .toList();
    if (missing.isNotEmpty) await backend.block([], missing);
  }

  Future<void> refresh() async {
    domains = await backend.blockedDomains();
    apps = await backend.blockedApps();
    serviceEnabled = await backend.isServiceEnabled();
    schedules = await backend.schedules();
    running = await backend.scheduleStatus();
    loaded = true;
    notifyListeners();
  }

  Future<void> block(List<Site> toBlock) async {
    await backend.block(
      toBlock.expand((s) => s.domains).toList(),
      toBlock.expand((s) => s.apps).toList(),
    );
    await refresh();
  }

  Future<bool> unblock(String password, List<Site> toUnblock) async {
    final ok = await backend.unblock(
      password,
      toUnblock.expand((s) => s.domains).toList(),
      toUnblock.expand((s) => s.apps).toList(),
    );
    await refresh();
    return ok;
  }

  /// Sites blocked by schedules running now (on top of manual blocks).
  List<Site> get scheduledSites {
    final ids = {for (final r in running) r.id};
    final names = {
      for (final s in schedules)
        if (ids.contains(s.id)) ...s.sites,
    };
    return sites.where((s) => names.contains(s.name)).toList();
  }

  /// When every running schedule will have ended, or null if none is running.
  DateTime? get scheduledUntil => running.isEmpty
      ? null
      : running.map((r) => r.until).reduce((a, b) => a.isAfter(b) ? a : b);

  /// "Block now for…": a one-off schedule from now until [endsAt]. Stacks on
  /// top of anything already blocked (decision D2). One-off schedules that
  /// have finished are tidied away at the same time.
  Future<void> blockNow(List<Site> picked, DateTime endsAt) async {
    final start = now();
    final current = await backend.schedules();
    final kept = current.where(
      (s) => s.plan is! ForPlan || (s.plan as ForPlan).endsAt.isAfter(start),
    );
    final schedule = Schedule(
      id: newScheduleId('now'),
      name: 'Block now',
      sites: [for (final s in picked) s.name],
      domains: [for (final s in picked) ...s.domains],
      apps: [for (final s in picked) ...s.apps],
      plan: ForPlan(startsAt: start, endsAt: endsAt),
    );
    await backend.saveSchedules([...kept, schedule]);
    await refresh();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.resumed) refresh();
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    super.dispose();
  }
}

final _random = Random.secure();

/// A schedule id unique enough that two made in the same instant differ
/// (androidlib rejects duplicate ids).
String newScheduleId(String prefix) =>
    '$prefix-${DateTime.now().microsecondsSinceEpoch}-${_random.nextInt(1 << 32).toRadixString(36)}';
