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

  /// Replaces every schedule.
  Future<void> saveSchedules(List<Schedule> schedules);

  /// Ends a running schedule early (just the current occurrence). False if
  /// the password is wrong or it isn't running.
  Future<bool> pauseSchedule(String id, String password);
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
  Future<void> saveSchedules(List<Schedule> schedules) =>
      _channel.invokeMethod('saveSchedules', {
        'json': jsonEncode([for (final s in schedules) s.toJson()]),
      });

  @override
  Future<bool> pauseSchedule(String id, String password) async =>
      await _channel.invokeMethod<bool>('pauseSchedule', {
        'id': id,
        'password': password,
      }) ??
      false;
}
