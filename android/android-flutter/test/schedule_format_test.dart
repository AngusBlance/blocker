import 'package:blocker_flutter/schedule.dart';
import 'package:blocker_flutter/schedule_format.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('days read as words when they can, letters otherwise', () {
    expect(formatDays({1, 2, 3, 4, 5, 6, 7}), 'every day');
    expect(formatDays({1, 2, 3, 4, 5}), 'weekdays');
    expect(formatDays({6, 7}), 'weekends');
    expect(formatDays({1, 3, 5}), 'M W F');
    expect(formatDays({7, 1}), 'M S'); // Monday first, Sunday last
    expect(formatDays({2, 4}), 'T T');
  });

  test('ranges: daytime, overnight says next day, start == end is all day', () {
    expect(
      formatRange(EveryPlan(days: {1}, start: 540, end: 1020)),
      '09:00–17:00',
    );
    expect(
      formatRange(EveryPlan(days: {1}, start: 1320, end: 420)),
      '22:00–07:00 next day',
    );
    expect(formatRange(EveryPlan(days: {1}, start: 0, end: 0)), 'all day');
    expect(formatMinute(5), '00:05');
    expect(formatMinute(23 * 60 + 59), '23:59');
  });

  test('a whole plan on one line', () {
    expect(
      formatEvery(EveryPlan(days: {1, 2, 3, 4, 5}, start: 540, end: 1020)),
      'weekdays · 09:00–17:00',
    );
  });

  test('presets are valid plans', () {
    expect(schedulePresets.map((p) => p.label), [
      'work 9–5',
      'evenings',
      'bedtime',
    ]);
    expect(
      formatEvery(schedulePresets[2].plan),
      'M T W T S · 22:00–07:00 next day',
    );
  });
}
