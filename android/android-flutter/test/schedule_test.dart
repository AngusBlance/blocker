import 'dart:convert';
import 'dart:io';

import 'package:blocker_flutter/schedule.dart';
import 'package:flutter_test/flutter_test.dart';

/// The same fixture androidlib's ScheduleTest.kt parses, so the Dart and
/// Kotlin JSON formats can't drift apart.
List<Schedule> loadFixture() {
  final text = File('../androidlib/src/test/resources/schedules.json')
      .readAsStringSync();
  return [
    for (final item in jsonDecode(text) as List)
      Schedule.fromJson(item as Map<String, Object?>),
  ];
}

void main() {
  test('parses the shared fixture into every plan and action type', () {
    final schedules = {for (final s in loadFixture()) s.id: s};
    expect(schedules.keys, ['work', 'bedtime', 'focus', 'weekend']);

    final work = schedules['work']!;
    expect(
      work.pausedUntil,
      DateTime.fromMillisecondsSinceEpoch(1760000000000),
    );
    expect(work.plan, EveryPlan(days: {1, 2, 3, 4, 5}, start: 540, end: 1020));
    expect(work.action, const BlockAction());
    expect(work.domains, ['youtube.com', 'googlevideo.com']);

    final bedtime = schedules['bedtime']!;
    expect((bedtime.plan as EveryPlan).overnight, isTrue);
    expect(bedtime.action, const MessageAction('go to bed'));

    final focus = schedules['focus']!;
    expect(
      focus.plan,
      ForPlan(
        startsAt: DateTime.fromMillisecondsSinceEpoch(1760000000000),
        endsAt: DateTime.fromMillisecondsSinceEpoch(1760003600000),
      ),
    );
    expect(focus.action, const RedirectAction('com.amazon.kindle'));

    final weekend = schedules['weekend']!;
    expect(weekend.enabled, isFalse);
    expect((weekend.plan as EveryPlan).allDay, isTrue);
  });

  test('toJson matches the fixture exactly', () {
    final text = File('../androidlib/src/test/resources/schedules.json')
        .readAsStringSync();
    final raw = jsonDecode(text) as List;
    final schedules = loadFixture();
    for (var i = 0; i < raw.length; i++) {
      expect(jsonDecode(jsonEncode(schedules[i].toJson())), raw[i]);
    }
  });

  test('json round trips', () {
    for (final s in loadFixture()) {
      expect(
        Schedule.fromJson(
          jsonDecode(jsonEncode(s.toJson())) as Map<String, Object?>,
        ),
        s,
      );
    }
  });

  test('invalid plans are rejected', () {
    expect(() => EveryPlan(days: {}, start: 0, end: 60), throwsArgumentError);
    expect(() => EveryPlan(days: {8}, start: 0, end: 60), throwsArgumentError);
    expect(
      () => EveryPlan(days: {1}, start: 0, end: 1440),
      throwsArgumentError,
    );
    final t = DateTime(2026, 10, 15, 12);
    expect(() => ForPlan(startsAt: t, endsAt: t), throwsArgumentError);
  });

  test('unknown plan or action types are rejected', () {
    final json = loadFixture().first.toJson();
    expect(
      () => Schedule.fromJson({
        ...json,
        'plan': {'type': 'sometimes'},
      }),
      throwsFormatException,
    );
    expect(
      () => Schedule.fromJson({
        ...json,
        'action': {'type': 'explode'},
      }),
      throwsFormatException,
    );
  });

  test('copyWith keeps the id and changes only what is given', () {
    final work = loadFixture().first;
    final off = work.copyWith(enabled: false);
    expect(off.id, work.id);
    expect(off.enabled, isFalse);
    expect(off.plan, work.plan);
  });

  test('times keep only whole milliseconds, so a schedule equals itself after saving', () {
    final now = DateTime.now();
    final plan = ForPlan(
      startsAt: now,
      endsAt: now.add(const Duration(hours: 1)),
    );
    expect(plan.startsAt.microsecond, 0);
    final schedule = loadFixture()[2].copyWith(plan: plan, pausedUntil: now);
    final reloaded = Schedule.fromJson(
      jsonDecode(jsonEncode(schedule.toJson())) as Map<String, Object?>,
    );
    expect(reloaded, schedule);
    expect(reloaded.hashCode, schedule.hashCode);
  });

  test(
    'a sub-millisecond "for" plan is rejected instead of saving as zero length',
    () {
      final t = DateTime.fromMicrosecondsSinceEpoch(1760000000000000);
      expect(
        () => ForPlan(
          startsAt: t,
          endsAt: t.add(const Duration(microseconds: 300)),
        ),
        throwsArgumentError,
      );
    },
  );

  test('malformed values throw FormatException', () {
    final base = loadFixture().first.toJson();
    Map<String, Object?> plan(Map<String, Object?> change) => {
      ...base,
      'plan': {...base['plan']! as Map<String, Object?>, ...change},
    };
    for (final bad in <Map<String, Object?>>[
      {...base, 'id': 123},
      {...base, 'name': null},
      {...base}..remove('domains'),
      {
        ...base,
        'apps': [1, 2],
      },
      {...base, 'enabled': 'yes'},
      {...base, 'pausedUntil': 'soon'},
      plan({'start': 540.5}),
      plan({'start': '540'}),
      plan({
        'days': ['1'],
      }),
      {...base, 'plan': 'every'},
    ]) {
      expect(
        () => Schedule.fromJson(bad),
        throwsFormatException,
        reason: '$bad',
      );
    }
  });

  test('lists and days cannot be changed after creation', () {
    final work = loadFixture().first;
    expect(() => work.sites.add('x'), throwsUnsupportedError);
    expect(() => (work.plan as EveryPlan).days.add(6), throwsUnsupportedError);
  });

  test('copyWith can clear a pause', () {
    final work = loadFixture().first;
    expect(work.pausedUntil, isNotNull);
    expect(work.copyWith(clearPause: true).pausedUntil, isNull);
  });
}
