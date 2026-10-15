import 'package:blocker_flutter/backend.dart';
import 'package:blocker_flutter/main.dart';
import 'package:blocker_flutter/schedule.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';

const password = 'secret-unlock-password';

/// Stands in for androidlib: an in-memory block list.
class FakeBackend implements Backend {
  FakeBackend({this.serviceOn = true, this.sdk = 35});

  final Set<String> domains = {};
  final Set<String> apps = {};
  bool serviceOn;
  int sdk;
  int accessibilityOpened = 0;
  int appInfoOpened = 0;

  @override
  Future<List<String>> blockedDomains() async => domains.toList()..sort();

  @override
  Future<List<String>> blockedApps() async => apps.toList()..sort();

  @override
  Future<void> block(List<String> d, List<String> a) async {
    domains.addAll(d);
    apps.addAll(a);
  }

  @override
  Future<bool> unblock(String typed, List<String> d, List<String> a) async {
    if (typed != password) return false;
    domains.removeAll(d);
    apps.removeAll(a);
    return true;
  }

  @override
  Future<String> unlockPassword() async => password;

  @override
  Future<bool> isServiceEnabled() async => serviceOn;

  @override
  Future<int> sdkInt() async => sdk;

  @override
  Future<void> openAccessibilitySettings() async => accessibilityOpened++;

  @override
  Future<void> openAppInfo() async => appInfoOpened++;

  List<Schedule> savedSchedules = [];

  /// The fake's clock.
  DateTime Function() clock = DateTime.now;

  @override
  Future<List<Schedule>> schedules() async => savedSchedules;

  /// Mirrors androidlib's ScheduleRules.replaceAll: duplicate ids are bad,
  /// pauses only come from pausing, and without the password a running
  /// schedule must survive unweakened.
  @override
  Future<void> saveSchedules(
    List<Schedule> schedules, {
    String? password,
  }) async {
    final next = {for (final s in schedules) s.id: s};
    if (next.length != schedules.length) {
      throw PlatformException(code: 'bad_schedules', message: 'duplicate ids');
    }
    final stored = {for (final s in savedSchedules) s.id: s};
    if (password != _unlockPasswordForTests) {
      for (final running in savedSchedules.where(
        (s) => fakeActiveUntil(s, clock()) != null,
      )) {
        final kept = next[running.id];
        final ok =
            kept != null &&
            kept.enabled &&
            kept.plan == running.plan &&
            (kept.action == running.action ||
                kept.action == const BlockAction()) &&
            running.domains.every(kept.domains.contains) &&
            running.apps.every(kept.apps.contains);
        if (!ok) throw ScheduleLockedException('"${running.name}" is running');
      }
    }
    savedSchedules = [
      for (final s in schedules)
        stored[s.id]?.pausedUntil == null
            ? s.copyWith(clearPause: true)
            : s.copyWith(pausedUntil: stored[s.id]!.pausedUntil),
    ];
  }

  @override
  Future<List<RunningSchedule>> scheduleStatus() async => [
    for (final s in savedSchedules)
      if (fakeActiveUntil(s, clock()) case final until?)
        RunningSchedule(s.id, until),
  ];

  List<InstalledApp> launchableApps = const [
    InstalledApp('com.duolingo', 'Duolingo'),
    InstalledApp('com.amazon.kindle', 'Kindle'),
    InstalledApp('com.google.android.keep', 'Keep Notes'),
  ];

  @override
  Future<List<InstalledApp>> installedApps() async => launchableApps;

  /// Mirrors androidlib's ScheduleRules.next: soonest start among schedules
  /// not running now.
  @override
  Future<RunningSchedule?> nextSchedule() async {
    final now = clock();
    RunningSchedule? soonest;
    for (final s in savedSchedules) {
      if (fakeActiveUntil(s, now) != null) continue;
      final at = fakeNextStart(s, now);
      if (at != null && (soonest == null || at.isBefore(soonest.until))) {
        soonest = RunningSchedule(s.id, at);
      }
    }
    return soonest;
  }

  @override
  Future<PauseResult> pauseSchedule(String id, String typed) async {
    if (typed != password) return PauseResult.wrongPassword;
    final i = savedSchedules.indexWhere((s) => s.id == id);
    final until = i < 0 ? null : fakeActiveUntil(savedSchedules[i], clock());
    if (until == null) return PauseResult.notRunning;
    savedSchedules[i] = savedSchedules[i].copyWith(pausedUntil: until);
    return PauseResult.paused;
  }
}

const _unlockPasswordForTests = password;

/// A test-only copy of androidlib's Schedule.isActive / activeUntil (the real
/// rules live in Kotlin and are tested there), good enough for local times
/// without DST changes. Null when not running.
DateTime? fakeActiveUntil(Schedule s, DateTime now) {
  if (!s.enabled) return null;
  if (s.pausedUntil != null && now.isBefore(s.pausedUntil!)) return null;
  switch (s.plan) {
    case ForPlan(:final startsAt, :final endsAt):
      return !now.isBefore(startsAt) && now.isBefore(endsAt) ? endsAt : null;
    case EveryPlan(:final days, :final start, :final end):
      final minute = now.hour * 60 + now.minute;
      final today = DateTime(now.year, now.month, now.day);
      DateTime at(DateTime day, int m) =>
          DateTime(day.year, day.month, day.day, m ~/ 60, m % 60);
      final yesterday = now.weekday == 1 ? 7 : now.weekday - 1;
      if (start == end) {
        return days.contains(now.weekday)
            ? DateTime(now.year, now.month, now.day + 1)
            : null;
      }
      if (start < end) {
        return days.contains(now.weekday) && minute >= start && minute < end
            ? at(today, end)
            : null;
      }
      if (days.contains(now.weekday) && minute >= start) {
        return at(DateTime(now.year, now.month, now.day + 1), end);
      }
      if (days.contains(yesterday) && minute < end) return at(today, end);
      return null;
  }
}

Future<FakeBackend> pump(
  WidgetTester tester, {
  FakeBackend? backend,
  DateTime Function()? clock,
}) async {
  final b = backend ?? FakeBackend();
  if (clock != null) b.clock = clock;
  tester.view.physicalSize = const Size(1080, 2400);
  tester.view.devicePixelRatio = 2.6;
  addTearDown(tester.view.reset);
  await tester.pumpWidget(BlockerApp(backend: b, clock: clock));
  await tester.pumpAndSettle();
  return b;
}

Future<void> tapTab(WidgetTester tester, String label) async {
  await tester.tap(find.byKey(Key('tab-$label')));
  await tester.pumpAndSettle();
}

/// A test-only copy of androidlib's Schedule.nextStart.
DateTime? fakeNextStart(Schedule s, DateTime now) {
  if (!s.enabled) return null;
  bool usable(DateTime t) =>
      t.isAfter(now) && (s.pausedUntil == null || !t.isBefore(s.pausedUntil!));
  switch (s.plan) {
    case ForPlan(:final startsAt):
      return usable(startsAt) ? startsAt : null;
    case EveryPlan(:final days, :final start):
      for (var i = 0; i <= 14; i++) {
        final day = DateTime(now.year, now.month, now.day + i);
        if (!days.contains(day.weekday)) continue;
        final t = DateTime(
          day.year,
          day.month,
          day.day,
          start ~/ 60,
          start % 60,
        );
        if (usable(t)) return t;
      }
      return null;
  }
}
