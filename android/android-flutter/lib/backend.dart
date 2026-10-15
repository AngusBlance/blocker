import 'dart:convert';

import 'package:flutter/services.dart';

import 'schedule.dart';

/// What the UI needs from androidlib. The real one talks to MainActivity's
/// method channel; tests swap in a fake.
abstract class Backend {
  Future<List<String>> blockedDomains();
  Future<List<String>> blockedApps();
  Future<void> block(List<String> domains, List<String> apps);

  /// False (and nothing changes) if the password is wrong.
  Future<bool> unblock(
    String password,
    List<String> domains,
    List<String> apps,
  );
  Future<String> unlockPassword();
  Future<bool> isServiceEnabled();
  Future<int> sdkInt();
  Future<void> openAccessibilitySettings();
  Future<void> openAppInfo();

  Future<List<Schedule>> schedules();

  /// Replaces every schedule. Throws [ScheduleLockedException] if that would
  /// weaken a schedule that's running now and [password] isn't the unlock
  /// password.
  Future<void> saveSchedules(List<Schedule> schedules, {String? password});

  /// Ends a running schedule early (just the current occurrence).
  Future<PauseResult> pauseSchedule(String id, String password);

  /// Schedules running now, with when each one's current occurrence ends.
  Future<List<RunningSchedule>> scheduleStatus();

  /// The schedule that starts soonest among those not running, if any.
  Future<RunningSchedule?> nextSchedule();

  /// Apps a schedule can send you to instead (launchable, not Blocker).
  Future<List<InstalledApp>> installedApps();
}

class InstalledApp {
  const InstalledApp(this.packageName, this.label);

  final String packageName;
  final String label;
}

class RunningSchedule {
  const RunningSchedule(this.id, this.until);

  final String id;
  final DateTime until;

  @override
  bool operator ==(Object other) =>
      other is RunningSchedule &&
      other.id == id &&
      other.until.isAtSameMomentAs(until);

  @override
  int get hashCode => Object.hash(id, until.millisecondsSinceEpoch);
}

enum PauseResult { paused, wrongPassword, notRunning }

/// Saving would remove, disable or weaken a schedule that's running now.
class ScheduleLockedException implements Exception {
  ScheduleLockedException(this.message);

  final String message;

  @override
  String toString() => message;
}

class ChannelBackend implements Backend {
  static const _channel = MethodChannel('com.angusblance.blocker/backend');

  Future<List<String>> _strings(String method) async =>
      (await _channel.invokeListMethod<String>(method)) ?? [];

  @override
  Future<List<String>> blockedDomains() => _strings('getBlockedDomains');

  @override
  Future<List<String>> blockedApps() => _strings('getBlockedApps');

  @override
  Future<void> block(List<String> domains, List<String> apps) =>
      _channel.invokeMethod('block', {'domains': domains, 'apps': apps});

  @override
  Future<bool> unblock(
    String password,
    List<String> domains,
    List<String> apps,
  ) async =>
      await _channel.invokeMethod<bool>('unblock', {
        'password': password,
        'domains': domains,
        'apps': apps,
      }) ??
      false;

  @override
  Future<String> unlockPassword() async =>
      await _channel.invokeMethod<String>('getUnlockPassword') ?? '';

  @override
  Future<bool> isServiceEnabled() async =>
      await _channel.invokeMethod<bool>('isServiceEnabled') ?? false;

  @override
  Future<int> sdkInt() async => await _channel.invokeMethod<int>('sdkInt') ?? 0;

  @override
  Future<void> openAccessibilitySettings() =>
      _channel.invokeMethod('openAccessibilitySettings');

  @override
  Future<void> openAppInfo() => _channel.invokeMethod('openAppInfo');

  // Schedules travel as the JSON schedule.dart and androidlib's Schedule.kt share.
  @override
  Future<List<Schedule>> schedules() async {
    final json = await _channel.invokeMethod<String>('getSchedules') ?? '[]';
    return [
      for (final item in jsonDecode(json) as List)
        Schedule.fromJson(item as Map<String, Object?>),
    ];
  }

  @override
  Future<void> saveSchedules(
    List<Schedule> schedules, {
    String? password,
  }) async {
    try {
      await _channel.invokeMethod('saveSchedules', {
        'json': jsonEncode([for (final s in schedules) s.toJson()]),
        'password': password,
      });
    } on PlatformException catch (e) {
      if (e.code == 'locked') {
        throw ScheduleLockedException(e.message ?? 'schedule is running');
      }
      rethrow;
    }
  }

  @override
  Future<PauseResult> pauseSchedule(String id, String password) async {
    final result = await _channel.invokeMethod<String>('pauseSchedule', {
      'id': id,
      'password': password,
    });
    return switch (result) {
      'paused' => PauseResult.paused,
      'wrong_password' => PauseResult.wrongPassword,
      _ => PauseResult.notRunning,
    };
  }

  @override
  Future<List<RunningSchedule>> scheduleStatus() async {
    final json = await _channel.invokeMethod<String>('scheduleStatus') ?? '[]';
    return [
      for (final item in jsonDecode(json) as List)
        switch (item) {
          {'id': final String id, 'until': final int until} => RunningSchedule(
            id,
            DateTime.fromMillisecondsSinceEpoch(until),
          ),
          _ => throw FormatException('bad schedule status: $item'),
        },
    ];
  }

  @override
  Future<List<InstalledApp>> installedApps() async {
    final apps =
        await _channel.invokeListMethod<Map<Object?, Object?>>(
          'installedApps',
        ) ??
        [];
    return [
      for (final app in apps)
        if (app case {'package': final String pkg, 'label': final String label})
          InstalledApp(pkg, label),
    ];
  }

  /// Reuses [RunningSchedule]: `until` is when it starts.
  @override
  Future<RunningSchedule?> nextSchedule() async {
    final json = await _channel.invokeMethod<String>('nextSchedule');
    if (json == null) return null;
    return switch (jsonDecode(json)) {
      null => null,
      {'id': final String id, 'at': final int at} => RunningSchedule(
        id,
        DateTime.fromMillisecondsSinceEpoch(at),
      ),
      final other => throw FormatException('bad next schedule: $other'),
    };
  }
}
