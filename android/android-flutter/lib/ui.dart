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
