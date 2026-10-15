import 'dart:convert';

import 'package:blocker_flutter/backend.dart';
import 'package:blocker_flutter/schedule.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';

/// Checks exactly what ChannelBackend sends to and reads from MainActivity.kt.
void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  const channel = MethodChannel('com.angusblance.blocker/backend');
  final calls = <MethodCall>[];
  late Object? reply;

  setUp(() {
    calls.clear();
    reply = null;
    TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
        .setMockMethodCallHandler(channel, (call) async {
          calls.add(call);
          return reply;
        });
  });

  final work = Schedule(
    id: 'work',
    name: 'Work',
    sites: ['YouTube'],
    domains: ['youtube.com'],
    apps: ['com.google.android.youtube'],
    plan: EveryPlan(days: {1, 2, 3, 4, 5}, start: 540, end: 1020),
  );

  test('saveSchedules sends the whole list as one JSON string', () async {
    await ChannelBackend().saveSchedules([work]);
    expect(calls.single.method, 'saveSchedules');
    final json = (calls.single.arguments as Map)['json'] as String;
    expect(jsonDecode(json), [work.toJson()]);
  });

  test('schedules parses the JSON androidlib returns', () async {
    reply = jsonEncode([work.toJson()]);
    expect(await ChannelBackend().schedules(), [work]);
    reply = null; // nothing stored yet
    expect(await ChannelBackend().schedules(), isEmpty);
  });

  test('pauseSchedule passes id and password and returns the result', () async {
    reply = true;
    expect(await ChannelBackend().pauseSchedule('work', 'pw'), isTrue);
    expect(calls.single.method, 'pauseSchedule');
    expect(calls.single.arguments, {'id': 'work', 'password': 'pw'});
    reply = false;
    expect(await ChannelBackend().pauseSchedule('work', 'nope'), isFalse);
  });
}
