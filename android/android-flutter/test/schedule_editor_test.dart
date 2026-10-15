import 'package:blocker_flutter/schedule.dart';
import 'package:blocker_flutter/screens/schedule_editor.dart';
import 'package:blocker_flutter/sites.dart';
import 'package:blocker_flutter/theme.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

class Harness {
  Schedule? saved;
  bool deleted = false;
  final picks = <TimeOfDay>[];
}

Future<Harness> pumpEditor(
  WidgetTester tester, {
  Schedule? initial,
  bool canDelete = false,
}) async {
  final h = Harness();
  tester.view.physicalSize = const Size(1080, 2400);
  tester.view.devicePixelRatio = 2.6;
  addTearDown(tester.view.reset);
  await tester.pumpWidget(
    MaterialApp(
      theme: buildTheme(),
      home: Scaffold(
        body: ScheduleEditor(
          initial: initial,
          newId: () => 'new-id',
          onSave: (s) async => h.saved = s,
          onDelete: canDelete ? () async => h.deleted = true : null,
          pickTime: (context, initial) async =>
              h.picks.isEmpty ? null : h.picks.removeAt(0),
        ),
      ),
    ),
  );
  return h;
}

Future<void> tapKey(WidgetTester tester, String key) async {
  await tester.ensureVisible(find.byKey(Key(key)));
  await tester.pumpAndSettle();
  await tester.tap(find.byKey(Key(key)));
  await tester.pumpAndSettle();
}

String summary(WidgetTester tester) =>
    tester.widget<Text>(find.byKey(const Key('plan-summary'))).data!;

void main() {
  testWidgets('one tap on a preset, pick a site, save', (tester) async {
    final h = await pumpEditor(tester);
    await tapKey(tester, 'preset-work 9–5');
    expect(summary(tester), 'weekdays · 09:00–17:00');
    await tapKey(tester, 'site-chip-YouTube');
    await tapKey(tester, 'save-schedule');
    final s = h.saved!;
    expect(s.id, 'new-id');
    expect(s.name, 'work 9–5');
    expect(s.plan, EveryPlan(days: {1, 2, 3, 4, 5}, start: 540, end: 1020));
    expect(s.sites, ['YouTube']);
    expect(s.domains, sites.first.domains);
    expect(s.apps, sites.first.apps);
    expect(s.enabled, isTrue);
  });

  testWidgets('editing days and times saves the right plan', (tester) async {
    final h = await pumpEditor(tester);
    await tester.enterText(find.byKey(const Key('schedule-name')), 'gym');
    await tapKey(tester, 'days-weekends');
    await tapKey(tester, 'day-3'); // add Wednesday
    h.picks.addAll([
      const TimeOfDay(hour: 6, minute: 30),
      const TimeOfDay(hour: 8, minute: 15),
    ]);
    await tapKey(tester, 'time-from');
    await tapKey(tester, 'time-to');
    expect(summary(tester), 'W S S · 06:30–08:15');
    await tapKey(tester, 'site-chip-Netflix');
    await tapKey(tester, 'save-schedule');
    expect(h.saved!.plan, EveryPlan(days: {3, 6, 7}, start: 390, end: 495));
    expect(h.saved!.name, 'gym');
  });

  testWidgets('an overnight range says next day', (tester) async {
    final h = await pumpEditor(tester);
    h.picks.addAll([
      const TimeOfDay(hour: 22, minute: 0),
      const TimeOfDay(hour: 7, minute: 0),
    ]);
    await tapKey(tester, 'time-from');
    await tapKey(tester, 'time-to');
    expect(summary(tester), 'weekdays · 22:00–07:00 next day');
    await tapKey(tester, 'preset-bedtime');
    expect(summary(tester), 'M T W T S · 22:00–07:00 next day');
  });

  testWidgets('all day turns the times off and back on', (tester) async {
    final h = await pumpEditor(tester);
    await tapKey(tester, 'all-day');
    expect(summary(tester), 'weekdays · all day');
    h.picks.add(const TimeOfDay(hour: 1, minute: 0));
    await tapKey(tester, 'time-from'); // disabled: no pick happens
    expect(h.picks, hasLength(1));
    await tapKey(tester, 'all-day');
    expect(summary(tester), 'weekdays · 09:00–17:00');
  });

  testWidgets('cancelling the time picker changes nothing', (tester) async {
    await pumpEditor(tester);
    await tapKey(tester, 'time-from'); // stub returns null
    expect(summary(tester), 'weekdays · 09:00–17:00');
  });

  testWidgets('save waits for a name, a day and a site', (tester) async {
    final h = await pumpEditor(tester);
    await tapKey(tester, 'save-schedule');
    expect(h.saved, isNull);
    expect(find.text('pick at least one site.'), findsOneWidget);
    await tapKey(tester, 'site-chip-TikTok');
    expect(find.text('give it a name.'), findsOneWidget);
    await tester.enterText(find.byKey(const Key('schedule-name')), 'x');
    for (var d = 1; d <= 5; d++) {
      await tapKey(tester, 'day-$d');
    }
    expect(find.text('pick at least one day.'), findsOneWidget);
    await tapKey(tester, 'save-schedule');
    expect(h.saved, isNull);
  });

  testWidgets('editing keeps id, on/off and any pause', (tester) async {
    final existing = Schedule(
      id: 'keep-me',
      name: 'Work',
      sites: ['YouTube'],
      domains: sites.first.domains,
      apps: sites.first.apps,
      plan: EveryPlan(days: {1, 2, 3, 4, 5}, start: 540, end: 1020),
      enabled: false,
      pausedUntil: DateTime(2026, 10, 15, 17),
    );
    final h = await pumpEditor(tester, initial: existing, canDelete: true);
    expect(find.text('EDIT SCHEDULE'), findsOneWidget);
    await tapKey(tester, 'day-6');
    await tapKey(tester, 'save-schedule');
    expect(h.saved!.id, 'keep-me');
    expect(h.saved!.enabled, isFalse);
    expect(h.saved!.pausedUntil, DateTime(2026, 10, 15, 17));
    expect((h.saved!.plan as EveryPlan).days, {1, 2, 3, 4, 5, 6});
    await tapKey(tester, 'delete-schedule');
    expect(h.deleted, isTrue);
  });
}
