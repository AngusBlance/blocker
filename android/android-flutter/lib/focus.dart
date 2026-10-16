/// Focus mode: until [endsAt], only the allowed sites and apps can be open
/// (androidlib's Focus.kt enforces it; this is the data).
class FocusSession {
  const FocusSession({
    required this.endsAt,
    required this.sites,
    required this.domains,
    required this.apps,
  });

  final DateTime endsAt;

  /// Site names as shown in the app, plus what they resolve to.
  final List<String> sites;
  final List<String> domains;

  /// Allowed apps' package names.
  final List<String> apps;

  Map<String, Object?> toJson() => {
    'endsAt': endsAt.millisecondsSinceEpoch,
    'sites': sites,
    'domains': domains,
    'apps': apps,
  };

  static FocusSession fromJson(Map<String, Object?> json) => switch (json) {
    {
      'endsAt': final int endsAt,
      'sites': final List<Object?> sites,
      'domains': final List<Object?> domains,
      'apps': final List<Object?> apps,
    } =>
      FocusSession(
        endsAt: DateTime.fromMillisecondsSinceEpoch(endsAt),
        sites: sites.cast<String>(),
        domains: domains.cast<String>(),
        apps: apps.cast<String>(),
      ),
    _ => throw FormatException('bad focus: $json'),
  };
}

enum FocusEndResult { ended, wrongPassword, notRunning }
