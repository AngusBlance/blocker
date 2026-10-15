import 'package:flutter/material.dart';

// Same palette as the TUI (Textual's dark theme):
// near-black background, square single-line borders, orange accent on
// whatever has focus, monospace text.
class AppColors {
  static const background = Color(0xFF121212);
  static const surface = Color(0xFF1E1E1E);
  static const panel = Color(0xFF24272B);
  static const foreground = Color(0xFFE0E0E0);
  static const muted = Color(0xFF8B8B8B);
  static const border = Color(0xFF3A3A3A);
  static const accent = Color(0xFFFFA62B);
  static const error = Color(0xFFBA3C5B);
  static const success = Color(0xFF4EBF71);
}

const mono = 'monospace';

TextStyle monoStyle({
  Color color = AppColors.foreground,
  double size = 14,
  bool bold = false,
}) => TextStyle(
  fontFamily: mono,
  fontSize: size,
  color: color,
  fontWeight: bold ? FontWeight.w700 : FontWeight.w400,
  height: 1.4,
);

ThemeData buildTheme() => ThemeData(
  brightness: Brightness.dark,
  scaffoldBackgroundColor: AppColors.background,
  fontFamily: mono,
  colorScheme: const ColorScheme.dark(
    primary: AppColors.accent,
    surface: AppColors.background,
    error: AppColors.error,
  ),
  textSelectionTheme: const TextSelectionThemeData(
    cursorColor: AppColors.accent,
    selectionColor: Color(0x55FFA62B),
  ),
);
