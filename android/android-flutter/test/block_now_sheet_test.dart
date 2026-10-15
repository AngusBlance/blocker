import 'package:blocker_flutter/screens/block_now_sheet.dart';
import 'package:blocker_flutter/sites.dart';
import 'package:blocker_flutter/theme.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

final now = DateTime(2026, 10, 15, 13, 30);

class Started {
  List<String> sites = [];
  DateTime? startsAt;
  DateTime? endsAt;
  Object? failWith;
}

Future<Started> pumpSheet(
  WidgetTester tester, {
  DateTime? at,
  Object? failWith,
}) async {
  final started = Started()..failWith = failWith;
  tester.view.physicalSize = const Size(1080, 2400);
  tester.view.devicePixelRatio = 2.6;
  addTearDown(tester.view.reset);
  await tester.pumpWidget(
    MaterialApp(
      theme: buildTheme(),
      home: Scaffold(
        body: BlockNowSheet(
          key: UniqueKey(),
          now: () => at ?? now,
          onStart: (picked, startsAt, endsAt) async {
            if (started.failWith != null) throw started.failWith!;
            started.sites = [for (final s in picked) s.name];
            started.startsAt = startsAt;
            started.endsAt = endsAt;
          },
        ),
      ),
    ),
  );
  return started;
}

Future<void> tap(WidgetTester tester, String key) async {
  await tester.ensureVisible(find.byKey(Key(key)));
  await tester.tap(find.byKey(Key(key)));
  await tester.pumpAndSettle();
}

String startLabel(WidgetTester tester) => tester
    .widgetList<Text>(
      find.descendant(
        of: find.byKey(const Key('start-block')),
        matching: find.byType(Text),
      ),
    )
    .single
    .data!;

String customLength(WidgetTester tester) =>
    tester.widget<Text>(find.byKey(const Key('custom-length'))).data!;

void main() {
  testWidgets('every site is picked and 1h is chosen to begin with', (
    tester,
  ) async {
    final started = await pumpSheet(tester);
    expect(startLabel(tester), 'block ${sites.length} sites for 1h');
    await tap(tester, 'start-block');
    expect(started.sites, [for (final s in sites) s.name]);
    expect(started.startsAt, now);
    expect(started.endsAt, DateTime(2026, 10, 15, 14, 30));
  });

  testWidgets('pick sites and a length: three taps', (tester) async {
    final started = await pumpSheet(tester);
    for (final s in sites.skip(2)) {
      await tap(tester, 'pick-${s.name}');
    }
    await tap(tester, 'length-30m');
    expect(startLabel(tester), 'block 2 sites for 30m');
    await tap(tester, 'start-block');
    expect(started.sites, [sites[0].name, sites[1].name]);
    expect(started.endsAt, DateTime(2026, 10, 15, 14));
  });

  testWidgets('until 7am is tomorrow in the afternoon, today before 7', (
    tester,
  ) async {
    var started = await pumpSheet(tester);
    await tap(tester, 'length-until 7am');
    expect(startLabel(tester), 'block ${sites.length} sites until 7am');
    await tap(tester, 'start-block');
    expect(started.endsAt, DateTime(2026, 10, 16, 7));

    started = await pumpSheet(tester, at: DateTime(2026, 10, 15, 5, 10));
    await tap(tester, 'length-until 7am');
    await tap(tester, 'start-block');
    expect(started.endsAt, DateTime(2026, 10, 15, 7));
  });

  testWidgets('custom length steps by 15 minutes between 15m and 12h', (
    tester,
  ) async {
    final started = await pumpSheet(tester);
    await tap(tester, 'length-custom');
    expect(customLength(tester), '45m');
    await tap(tester, 'custom-more');
    await tap(tester, 'custom-more');
    expect(customLength(tester), '1h 15m');
    expect(startLabel(tester), 'block ${sites.length} sites for 1h 15m');
    for (var i = 0; i < 10; i++) {
      await tap(tester, 'custom-less');
    }
    expect(customLength(tester), '15m'); // stops at the minimum
    await tap(tester, 'start-block');
    expect(started.endsAt, DateTime(2026, 10, 15, 13, 45));
  });

  testWidgets('start is disabled with no sites picked', (tester) async {
    final started = await pumpSheet(tester);
    for (final s in sites) {
      await tap(tester, 'pick-${s.name}');
    }
    await tap(tester, 'start-block');
    expect(started.endsAt, isNull);
  });

  testWidgets('until 7am less than half an hour before 7 means tomorrow', (
    tester,
  ) async {
    final started = await pumpSheet(tester, at: DateTime(2026, 10, 15, 6, 45));
    await tap(tester, 'length-until 7am');
    await tap(tester, 'start-block');
    expect(started.endsAt, DateTime(2026, 10, 16, 7));
  });

  testWidgets('if starting fails the error shows and start works again', (
    tester,
  ) async {
    await pumpSheet(tester, failWith: Exception('locked'));
    await tap(tester, 'start-block');
    expect(find.byKey(const Key('block-error')), findsOneWidget);
    expect(find.textContaining("couldn't start the block"), findsOneWidget);
    final button = tester.widget<InkWell>(
      find.descendant(
        of: find.byKey(const Key('start-block')),
        matching: find.byType(InkWell),
      ),
    );
    expect(button.onTap, isNotNull);
  });
}
