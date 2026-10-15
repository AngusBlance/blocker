import 'package:blocker_flutter/ui.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  final now = DateTime(2026, 10, 15, 13, 30); // a Thursday

  test('formatUntil: today, midnight, tomorrow, later in the week', () {
    expect(formatUntil(DateTime(2026, 10, 15, 17), now), '17:00');
    expect(formatUntil(DateTime(2026, 10, 16), now), 'midnight');
    expect(formatUntil(DateTime(2026, 10, 16, 7), now), 'tomorrow 07:00');
    expect(formatUntil(DateTime(2026, 10, 19, 9), now), 'Mon 09:00');
  });

  test('formatUntil counts calendar days across a DST change', () {
    // Spring forward (29 Mar 2026 in the UK): Saturday 23:30 to Sunday 23:00
    // is under 24 hours but still "tomorrow".
    expect(
      formatUntil(DateTime(2026, 3, 29, 23), DateTime(2026, 3, 28, 23, 30)),
      'tomorrow 23:00',
    );
  });

  test('formatDuration and formatClock', () {
    expect(formatDuration(const Duration(minutes: 45)), '45m');
    expect(formatDuration(const Duration(hours: 2)), '2h');
    expect(formatDuration(const Duration(minutes: 75)), '1h 15m');
    expect(formatClock(DateTime(2026, 1, 1, 7, 5)), '07:05');
  });

  test('formatRemaining rounds down to the minute', () {
    expect(formatRemaining(const Duration(seconds: 30)), 'under a minute');
    expect(formatRemaining(const Duration(minutes: 12, seconds: 59)), '12m');
    expect(formatRemaining(const Duration(hours: 1, minutes: 5)), '1h 05m');
    expect(formatRemaining(const Duration(hours: 26)), '26h 00m');
  });
}
