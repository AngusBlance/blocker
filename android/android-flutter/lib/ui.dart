import 'package:flutter/material.dart';

import 'theme.dart';

/// A bordered box like the TUI's panes. `focused` gives it the accent border
/// the TUI uses for the focused pane.
class Pane extends StatelessWidget {
  const Pane({
    super.key,
    this.title,
    required this.children,
    this.focused = false,
    this.error = false,
  });

  final String? title;
  final List<Widget> children;
  final bool focused;
  final bool error;

  @override
  Widget build(BuildContext context) {
    final borderColor = error
        ? AppColors.error
        : focused
        ? AppColors.accent
        : AppColors.border;
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
      decoration: BoxDecoration(
        color: AppColors.background,
        border: Border.all(color: borderColor),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          if (title != null)
            Text(
              title!.toUpperCase(),
              style: monoStyle(
                bold: true,
                color: error ? AppColors.error : AppColors.foreground,
              ),
            ),
          for (final child in children) ...[const SizedBox(height: 10), child],
        ],
      ),
    );
  }
}

class Muted extends StatelessWidget {
  const Muted(this.text, {super.key});

  final String text;

  @override
  Widget build(BuildContext context) =>
      Text(text, style: monoStyle(color: AppColors.muted));
}

/// One "key  value" line, like `  state           BLOCKED` on the TUI dashboard.
class Field extends StatelessWidget {
  const Field(
    this.label,
    this.value, {
    super.key,
    this.color = AppColors.foreground,
  });

  final String label;
  final String value;
  final Color color;

  @override
  Widget build(BuildContext context) => Row(
    children: [
      SizedBox(
        width: 120,
        child: Text(label, style: monoStyle(color: AppColors.muted)),
      ),
      Expanded(
        child: Text(value, style: monoStyle(color: color)),
      ),
    ],
  );
}

/// The settings path to follow, highlighted in the accent colour.
class PathBox extends StatelessWidget {
  const PathBox(this.path, {super.key});

  final String path;

  @override
  Widget build(BuildContext context) => Container(
    color: AppColors.surface,
    padding: const EdgeInsets.all(10),
    child: Text(path, style: monoStyle(color: AppColors.accent, bold: true)),
  );
}

class AppButton extends StatelessWidget {
  const AppButton(
    this.title, {
    super.key,
    required this.onPressed,
    this.primary = false,
  });

  final String title;
  final VoidCallback? onPressed;
  final bool primary;

  @override
  Widget build(BuildContext context) {
    final enabled = onPressed != null;
    return Opacity(
      opacity: enabled ? 1 : 0.35,
      child: Material(
        color: primary ? AppColors.accent : AppColors.surface,
        shape: RoundedRectangleBorder(
          side: BorderSide(
            color: primary ? AppColors.accent : AppColors.border,
          ),
        ),
        child: InkWell(
          onTap: onPressed,
          splashColor: Colors.white10,
          child: Padding(
            padding: const EdgeInsets.symmetric(vertical: 12),
            child: Center(
              child: Text(
                title,
                style: monoStyle(
                  bold: true,
                  color: primary ? AppColors.background : AppColors.foreground,
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}

/// A square toggle chip in the TUI style: `(x) label` with the accent border
/// when selected, `( ) label` when not. Used for picking sites, durations and
/// days.
class SquareChip extends StatelessWidget {
  const SquareChip(
    this.label, {
    super.key,
    required this.selected,
    required this.onTap,
    this.marker = true,
  });

  final String label;
  final bool selected;
  final VoidCallback onTap;

  /// Show the `(x)` / `( )` marker; off for single-choice chips like
  /// durations, where the border alone says which is picked.
  final bool marker;

  @override
  Widget build(BuildContext context) {
    return Semantics(
      label: label,
      selected: selected,
      checked: marker ? selected : null,
      inMutuallyExclusiveGroup: !marker,
      button: true,
      // The marker text is hidden from screen readers, so the tap has to be
      // put back on this node or the chip can't be activated.
      onTap: onTap,
      excludeSemantics: true,
      child: Material(
        color: selected ? AppColors.surface : AppColors.background,
        shape: RoundedRectangleBorder(
          side: BorderSide(
            color: selected ? AppColors.accent : AppColors.border,
          ),
        ),
        child: InkWell(
          onTap: onTap,
          // At least 48dp tall for touch, but only as wide as its label
          // (widthFactor 1), so chips sit side by side in a Wrap.
          child: ConstrainedBox(
            constraints: const BoxConstraints(minHeight: 48),
            child: Align(
              widthFactor: 1,
              child: Padding(
                padding: const EdgeInsets.symmetric(
                  horizontal: 12,
                  vertical: 10,
                ),
                child: Text(
                  marker ? '${selected ? '(x)' : '( )'} $label' : label,
                  style: monoStyle(
                    color: selected ? AppColors.accent : AppColors.foreground,
                    bold: selected,
                  ),
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}

/// "1h", "45m", "1h 30m".
String formatDuration(Duration d) {
  final h = d.inHours;
  final m = d.inMinutes % 60;
  if (h == 0) return '${m}m';
  if (m == 0) return '${h}h';
  return '${h}h ${m}m';
}

/// 24-hour "07:00".
String formatClock(DateTime t) =>
    '${t.hour.toString().padLeft(2, '0')}:${t.minute.toString().padLeft(2, '0')}';

/// When something ends, relative to [now]: "17:00", "midnight",
/// "tomorrow 07:00" or "Mon 07:00". Days are counted on calendar dates, so
/// a 23- or 25-hour DST day still counts as one.
String formatUntil(DateTime until, DateTime now) {
  final days = DateTime.utc(
    until.year,
    until.month,
    until.day,
  ).difference(DateTime.utc(now.year, now.month, now.day)).inDays;
  final midnight = until.hour == 0 && until.minute == 0;
  if (days <= 0) return formatClock(until);
  if (days == 1) {
    return midnight ? 'midnight' : 'tomorrow ${formatClock(until)}';
  }
  const names = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
  return '${names[until.weekday - 1]} ${formatClock(until)}';
}
