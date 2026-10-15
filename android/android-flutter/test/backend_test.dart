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
    final args = calls.single.arguments as Map;
    expect(jsonDecode(args['json'] as String), [work.toJson()]);
    expect(args['password'], isNull);
  });

  test('schedules parses the JSON androidlib returns', () async {
    reply = jsonEncode([work.toJson()]);
    expect(await ChannelBackend().schedules(), [work]);
    reply = null; // nothing stored yet
    expect(await ChannelBackend().schedules(), isEmpty);
  });

  test('saveSchedules sends the password when given', () async {
    await ChannelBackend().saveSchedules([work], password: 'pw');
    expect((calls.single.arguments as Map)['password'], 'pw');
  });

  test(
    'a locked save becomes ScheduleLockedException; other errors pass through',
    () async {
      final messenger =
          TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger;
      messenger.setMockMethodCallHandler(
        channel,
        (call) async => throw PlatformException(
          code: 'locked',
          message: '"Work" is running',
        ),
      );
      await expectLater(
        ChannelBackend().saveSchedules([work]),
        throwsA(
          isA<ScheduleLockedException>().having(
            (e) => e.message,
            'message',
            '"Work" is running',
          ),
        ),
      );
      messenger.setMockMethodCallHandler(
        channel,
        (call) async => throw PlatformException(code: 'bad_schedules'),
      );
      await expectLater(
        ChannelBackend().saveSchedules([work]),
        throwsA(isA<PlatformException>()),
      );
    },
  );

  test('pauseSchedule passes id and password and maps the result', () async {
    reply = 'paused';
    expect(
      await ChannelBackend().pauseSchedule('work', 'pw'),
      PauseResult.paused,
    );
    expect(calls.single.method, 'pauseSchedule');
    expect(calls.single.arguments, {'id': 'work', 'password': 'pw'});
    reply = 'wrong_password';
    expect(
      await ChannelBackend().pauseSchedule('work', 'nope'),
      PauseResult.wrongPassword,
    );
    reply = 'not_running';
    expect(
      await ChannelBackend().pauseSchedule('work', 'pw'),
      PauseResult.notRunning,
    );
  });

  test(
    'scheduleStatus parses ids and end times, and rejects bad entries',
    () async {
      reply = '[{"id":"work","until":1760000000000}]';
      expect(await ChannelBackend().scheduleStatus(), [
        RunningSchedule(
          'work',
          DateTime.fromMillisecondsSinceEpoch(1760000000000),
        ),
      ]);
      reply = '[{"id":"work"}]';
      await expectLater(
        ChannelBackend().scheduleStatus(),
        throwsFormatException,
      );
      reply = null;
      expect(await ChannelBackend().scheduleStatus(), isEmpty);
    },
  );
}
