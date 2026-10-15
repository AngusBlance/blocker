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

  /// Ids the fake treats as running now (androidlib works this out for real).
  Set<String> running = {};

  @override
  Future<List<Schedule>> schedules() async => savedSchedules;

  @override
  Future<void> saveSchedules(
    List<Schedule> schedules, {
    String? password,
  }) async {
    final next = {for (final s in schedules) s.id: s};
    if (next.length != schedules.length) {
      throw PlatformException(code: 'bad_schedules', message: 'duplicate ids');
    }
    for (final id in running) {
      final kept = next[id];
      if (password != _unlockPasswordForTests &&
          (kept == null || !kept.enabled)) {
        throw ScheduleLockedException('$id is running');
      }
    }
    savedSchedules = [...schedules];
  }

  /// The fake's clock, for working out which one-off blocks are running.
  DateTime Function() clock = DateTime.now;

  @override
  Future<List<RunningSchedule>> scheduleStatus() async {
    final now = clock();
    return [
      for (final s in savedSchedules)
        if (s.plan case ForPlan(:final startsAt, :final endsAt)
            when !now.isBefore(startsAt) && now.isBefore(endsAt))
          RunningSchedule(s.id, endsAt)
        else if (running.contains(s.id))
          RunningSchedule(s.id, now.add(const Duration(hours: 1))),
    ];
  }

  @override
  Future<PauseResult> pauseSchedule(String id, String typed) async {
    if (typed != password) return PauseResult.wrongPassword;
    if (!running.remove(id)) return PauseResult.notRunning;
    return PauseResult.paused;
  }
}

const _unlockPasswordForTests = password;

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
