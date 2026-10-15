import 'dart:async';
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
    _scheduleNextRefresh();
    notifyListeners();
  }

  Timer? _timer;

  /// Keeps the dashboard honest while it's open: refresh just after the
  /// soonest running schedule ends, and at least once a minute so schedules
  /// that start show up.
  void _scheduleNextRefresh() {
    _timer?.cancel();
    var wait = const Duration(minutes: 1);
    for (final r in running) {
      final untilEnd = r.until.difference(now()) + const Duration(seconds: 1);
      if (untilEnd < wait) {
        wait = untilEnd < Duration.zero ? Duration.zero : untilEnd;
      }
    }
    _timer = Timer(wait, () {
      if (_foreground) refresh();
    });
  }

  bool _foreground = true;

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

  /// Running schedules with their names, soonest-ending first, for the
  /// dashboard's one-row-each status.
  List<({String name, int siteCount, DateTime until})> get runningRows {
    final byId = {for (final s in schedules) s.id: s};
    final rows = [
      for (final r in running)
        if (byId[r.id] case final s?)
          (name: s.name, siteCount: s.sites.length, until: r.until),
    ]..sort((a, b) => a.until.compareTo(b.until));
    return rows;
  }

  bool isRunning(String id) => running.any((r) => r.id == id);

  DateTime? runningUntil(String id) {
    for (final r in running) {
      if (r.id == id) return r.until;
    }
    return null;
  }

  /// Adds [schedule], or replaces the one with the same id. Throws
  /// [ScheduleLockedException] if that would weaken a running schedule and
  /// [password] isn't the unlock password.
  Future<void> saveSchedule(Schedule schedule, {String? password}) async {
    final current = await backend.schedules();
    final i = current.indexWhere((s) => s.id == schedule.id);
    await backend.saveSchedules([
      for (final s in current) s.id == schedule.id ? schedule : s,
      if (i < 0) schedule,
    ], password: password);
    await refresh();
  }

  /// Deleting a running schedule needs the unlock password, like any other
  /// way of weakening it.
  Future<void> deleteSchedule(String id, {String? password}) async {
    final current = await backend.schedules();
    await backend.saveSchedules([
      for (final s in current)
        if (s.id != id) s,
    ], password: password);
    await refresh();
  }

  Future<void> setEnabled(
    Schedule schedule,
    bool enabled, {
    String? password,
  }) => saveSchedule(schedule.copyWith(enabled: enabled), password: password);

  /// Ends a running schedule early: just the current occurrence (D1).
  Future<PauseResult> endEarly(String id, String password) async {
    final result = await backend.pauseSchedule(id, password);
    await refresh();
    return result;
  }

  /// "Block now for…": a one-off schedule from [startsAt] until [endsAt].
  /// Stacks on top of anything already blocked (decision D2). One-off
  /// schedules that have finished are tidied away at the same time (all of
  /// them, not only "Block now" ones; a finished one-off never comes back).
  Future<void> blockNow(
    List<Site> picked,
    DateTime startsAt,
    DateTime endsAt,
  ) async {
    final start = startsAt;
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
    _foreground = state == AppLifecycleState.resumed;
    if (_foreground) refresh();
  }

  @override
  void dispose() {
    _timer?.cancel();
    WidgetsBinding.instance.removeObserver(this);
    super.dispose();
  }
}

final _random = Random.secure();

/// A schedule id unique enough that two made in the same instant differ
/// (androidlib rejects duplicate ids).
String newScheduleId(String prefix) =>
    '$prefix-${DateTime.now().microsecondsSinceEpoch}-${_random.nextInt(1 << 32).toRadixString(36)}';
