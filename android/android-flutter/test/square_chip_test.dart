import 'package:blocker_flutter/theme.dart';
import 'package:blocker_flutter/ui.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  testWidgets(
    'chips are 48dp tall but only as wide as their label, side by side',
    (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          theme: buildTheme(),
          home: Scaffold(
            body: SizedBox(
              width: 400,
              child: Wrap(
                children: [
                  SquareChip(
                    '15m',
                    key: const Key('a'),
                    marker: false,
                    selected: true,
                    onTap: () {},
                  ),
                  SquareChip(
                    '30m',
                    key: const Key('b'),
                    marker: false,
                    selected: false,
                    onTap: () {},
                  ),
                ],
              ),
            ),
          ),
        ),
      );
      final a = tester.getRect(find.byKey(const Key('a')));
      final b = tester.getRect(find.byKey(const Key('b')));
      expect(a.height, greaterThanOrEqualTo(48));
      expect(a.width, lessThan(200));
      expect(b.top, a.top); // same row
      expect(b.left, greaterThanOrEqualTo(a.right));
    },
  );

  testWidgets(
    'screen readers get the label and selected state, not the (x) marker',
    (tester) async {
      final handle = tester.ensureSemantics();
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: SquareChip('YouTube', selected: true, onTap: () {}),
          ),
        ),
      );
      expect(
        tester.getSemantics(find.byType(SquareChip)),
        isSemantics(
          label: 'YouTube',
          isButton: true,
          isSelected: true,
          hasCheckedState: true,
          isChecked: true,
          hasTapAction: true,
        ),
      );
      handle.dispose();
    },
  );
}
