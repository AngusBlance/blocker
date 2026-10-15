import 'schedule.dart';

/// How schedules read on screen, e.g. `M T W T F · 09:00–17:00`.

const _dayLetters = ['M', 'T', 'W', 'T', 'F', 'S', 'S'];

/// "every day", "weekdays", "weekends", or the selected days' letters in
/// order, e.g. "M W F".
String formatDays(Set<int> days) {
  if (days.length == 7) return 'every day';
  if (days.length == 5 && days.containsAll({1, 2, 3, 4, 5})) return 'weekdays';
  if (days.length == 2 && days.containsAll({6, 7})) return 'weekends';
  return [
    for (var d = 1; d <= 7; d++)
      if (days.contains(d)) _dayLetters[d - 1],
  ].join(' ');
}

/// "09:00".
String formatMinute(int minute) =>
    '${(minute ~/ 60).toString().padLeft(2, '0')}:${(minute % 60).toString().padLeft(2, '0')}';

/// "09:00–17:00", "22:00–07:00 next day" or "all day".
String formatRange(EveryPlan plan) {
  if (plan.allDay) return 'all day';
  final range = '${formatMinute(plan.start)}–${formatMinute(plan.end)}';
  return plan.overnight ? '$range next day' : range;
}

/// One line for a recurring plan: "weekdays · 09:00–17:00".
String formatEvery(EveryPlan plan) =>
    '${formatDays(plan.days)} · ${formatRange(plan)}';

/// Ready-made recurring plans, so most schedules are one tap.
class SchedulePreset {
  const SchedulePreset(this.label, this.days, this.start, this.end);

  final String label;
  final Set<int> days;
  final int start;
  final int end;

  EveryPlan get plan => EveryPlan(days: days, start: start, end: end);
}

const schedulePresets = [
  SchedulePreset('work 9–5', {1, 2, 3, 4, 5}, 9 * 60, 17 * 60),
  SchedulePreset('evenings', {1, 2, 3, 4, 5, 6, 7}, 18 * 60, 23 * 60),
  SchedulePreset('bedtime', {1, 2, 3, 4, 7}, 22 * 60, 7 * 60),
];
