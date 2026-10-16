import 'dart:convert';

import 'package:blocker_flutter/focus.dart';
import 'package:blocker_flutter/ui.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'fakes.dart';

final now = DateTime(2026, 10, 16, 9, 0);

Future<void> tapKey(WidgetTester tester, String key) async {
  await tester.ensureVisible(find.byKey(Key(key)));
  await tester.pumpAndSettle();
  await tester.tap(find.byKey(Key(key)));
  await tester.pumpAndSettle();
}

String field(WidgetTester tester, String text) =>
    tester.widget<Text>(find.textContaining(text)).data!;

void main() {
  testWidgets(
    'pick a site and an app, 25m, start: only those are allowed until it ends',
    (tester) async {
      final backend = await pump(tester, clock: () => now);
      await tapKey(tester, 'open-focus');
      expect(
        tester
            .widget<AppButton>(find.byKey(const Key('start-focus')))
            .onPressed,
        isNull,
        reason: "can't start with nothing allowed",
      );
      await tapKey(tester, 'focus-site-YouTube');
      await tapKey(tester, 'focus-add-app');
      await tapKey(tester, 'app-com.google.android.keep');
      expect(
        find.byKey(const Key('focus-app-com.google.android.keep')),
        findsOneWidget,
      );
      await tapKey(tester, 'focus-length-25m');
      await tapKey(tester, 'start-focus');

      final f = backend.storedFocus!;
      expect(f.endsAt, DateTime(2026, 10, 16, 9, 25));
      expect(f.sites, ['YouTube']);
      expect(f.domains, contains('youtube.com'));
      expect(
        f.apps,
        containsAll(['com.google.android.youtube', 'com.google.android.keep']),
      );

      expect(find.text('FOCUS'), findsOneWidget);
      expect(field(tester, 'until 09:25'), contains('25m left'));
      expect(find.text('YouTube + 1 app'), findsOneWidget);
      expect(find.byKey(const Key('open-focus')), findsNothing);
    },
  );

  testWidgets('ending focus early needs the password', (tester) async {
    final backend = FakeBackend()
      ..storedFocus = FocusSession(
        endsAt: DateTime(2026, 10, 16, 10),
        sites: const [],
        domains: const [],
        apps: const ['com.google.android.keep'],
      );
    await pump(tester, backend: backend, clock: () => now);
    expect(find.text('1 app'), findsOneWidget);

    await tapKey(tester, 'end-focus');
    await tapKey(tester, 'password-cancel');
    expect(backend.storedFocus, isNotNull); // cancelled: still on

    await tapKey(tester, 'end-focus');
    await tester.enterText(find.byKey(const Key('unlock-input')), password);
    await tapKey(tester, 'unlock-button');
    expect(backend.storedFocus, isNull);
    expect(find.text('focus ended.'), findsOneWidget);
    expect(find.byKey(const Key('open-focus')), findsOneWidget);
  });

  test('json matches what androidlib reads', () {
    final f = FocusSession(
      endsAt: DateTime.fromMillisecondsSinceEpoch(1760000000000),
      sites: const ['YouTube'],
      domains: const ['youtube.com'],
      apps: const ['com.google.android.youtube'],
    );
    final json = jsonDecode(jsonEncode(f.toJson())) as Map<String, Object?>;
    expect(json, {
      'endsAt': 1760000000000,
      'sites': ['YouTube'],
      'domains': ['youtube.com'],
      'apps': ['com.google.android.youtube'],
    });
    final back = FocusSession.fromJson(json);
    expect(back.endsAt, f.endsAt);
    expect(back.apps, f.apps);
    expect(() => FocusSession.fromJson({'endsAt': '1'}), throwsFormatException);
  });
}
