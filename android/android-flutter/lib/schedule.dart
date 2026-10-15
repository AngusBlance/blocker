/// A block that applies at certain times. The UI creates and edits these and
/// hands them to androidlib as JSON; androidlib's Schedule.kt decides when one
/// is active, since the accessibility service enforces it. The JSON format
/// must match Schedule.kt (both are tested against the same fixture).
///
/// Times are kept to whole milliseconds, which is all the JSON stores, so a
/// schedule always equals itself after being saved and loaded.
class Schedule {
  Schedule({
    required this.id,
    required this.name,
    required List<String> sites,
    required List<String> domains,
    required List<String> apps,
    required this.plan,
    this.action = const BlockAction(),
    this.enabled = true,
    DateTime? pausedUntil,
  }) : sites = List.unmodifiable(sites),
       domains = List.unmodifiable(domains),
       apps = List.unmodifiable(apps),
       pausedUntil = pausedUntil == null ? null : _toMillis(pausedUntil);

  final String id;
  final String name;

  /// Site names as shown in the UI, plus what they resolve to.
  final List<String> sites;
  final List<String> domains;
  final List<String> apps;
  final SchedulePlan plan;
  final ScheduleAction action;
  final bool enabled;

  /// Ended early (with the unlock password) until this time. For an `every`
  /// schedule that's the end of the current occurrence; it comes back next
  /// time.
  final DateTime? pausedUntil;

  Schedule copyWith({
    String? name,
    List<String>? sites,
    List<String>? domains,
    List<String>? apps,
    SchedulePlan? plan,
    ScheduleAction? action,
    bool? enabled,
    DateTime? pausedUntil,
    bool clearPause = false,
  }) => Schedule(
    id: id,
    name: name ?? this.name,
    sites: sites ?? this.sites,
    domains: domains ?? this.domains,
    apps: apps ?? this.apps,
    plan: plan ?? this.plan,
    action: action ?? this.action,
    enabled: enabled ?? this.enabled,
    pausedUntil: clearPause ? null : pausedUntil ?? this.pausedUntil,
  );

  Map<String, Object?> toJson() => {
    'id': id,
    'name': name,
    'sites': sites,
    'domains': domains,
    'apps': apps,
    'plan': plan.toJson(),
    'action': action.toJson(),
    'enabled': enabled,
    if (pausedUntil != null) 'pausedUntil': pausedUntil!.millisecondsSinceEpoch,
  };

  /// Throws [FormatException] for anything malformed.
  factory Schedule.fromJson(Map<String, Object?> json) => Schedule(
    id: _get<String>(json, 'id'),
    name: _get<String>(json, 'name'),
    sites: _strings(json, 'sites'),
    domains: _strings(json, 'domains'),
    apps: _strings(json, 'apps'),
    plan: SchedulePlan.fromJson(_get<Map<String, Object?>>(json, 'plan')),
    action: ScheduleAction.fromJson(_get<Map<String, Object?>>(json, 'action')),
    enabled: json.containsKey('enabled') ? _get<bool>(json, 'enabled') : true,
    pausedUntil: json.containsKey('pausedUntil')
        ? DateTime.fromMillisecondsSinceEpoch(_get<int>(json, 'pausedUntil'))
        : null,
  );

  @override
  bool operator ==(Object other) =>
      other is Schedule &&
      other.id == id &&
      other.name == name &&
      _listEquals(other.sites, sites) &&
      _listEquals(other.domains, domains) &&
      _listEquals(other.apps, apps) &&
      other.plan == plan &&
      other.action == action &&
      other.enabled == enabled &&
      other.pausedUntil?.millisecondsSinceEpoch ==
          pausedUntil?.millisecondsSinceEpoch;

  @override
  int get hashCode => Object.hash(
    id,
    name,
    plan,
    action,
    enabled,
    pausedUntil?.millisecondsSinceEpoch,
  );
}

sealed class SchedulePlan {
  const SchedulePlan();

  Map<String, Object?> toJson();

  /// Throws [FormatException] for anything malformed.
  factory SchedulePlan.fromJson(
    Map<String, Object?> json,
  ) => switch (_get<String>(json, 'type')) {
    'for' => ForPlan(
      startsAt: DateTime.fromMillisecondsSinceEpoch(
        _get<int>(json, 'startsAt'),
      ),
      endsAt: DateTime.fromMillisecondsSinceEpoch(_get<int>(json, 'endsAt')),
    ),
    'every' => EveryPlan(
      days: {
        for (final d in _get<List<Object?>>(json, 'days'))
          d is int
              ? d
              : throw FormatException('days should be whole numbers, got $d'),
      },
      start: _get<int>(json, 'start'),
      end: _get<int>(json, 'end'),
    ),
    final type => throw FormatException('unknown plan type $type'),
  };
}

/// "Block now for…": from [startsAt] until [endsAt].
class ForPlan extends SchedulePlan {
  ForPlan({required DateTime startsAt, required DateTime endsAt})
    : startsAt = _toMillis(startsAt),
      endsAt = _toMillis(endsAt) {
    if (!this.endsAt.isAfter(this.startsAt)) {
      throw ArgumentError('endsAt must be after startsAt');
    }
  }

  final DateTime startsAt;
  final DateTime endsAt;

  @override
  Map<String, Object?> toJson() => {
    'type': 'for',
    'startsAt': startsAt.millisecondsSinceEpoch,
    'endsAt': endsAt.millisecondsSinceEpoch,
  };

  @override
  bool operator ==(Object other) =>
      other is ForPlan &&
      other.startsAt.isAtSameMomentAs(startsAt) &&
      other.endsAt.isAtSameMomentAs(endsAt);

  @override
  int get hashCode => Object.hash(
    startsAt.millisecondsSinceEpoch,
    endsAt.millisecondsSinceEpoch,
  );
}

/// Every selected day (ISO: 1 = Monday … 7 = Sunday) from [start] to [end],
/// in minutes after midnight. end < start runs overnight; start == end means
/// the whole day.
class EveryPlan extends SchedulePlan {
  EveryPlan({required Set<int> days, required this.start, required this.end})
    : days = Set.unmodifiable(days) {
    if (days.isEmpty) throw ArgumentError('pick at least one day');
    if (days.any((d) => d < 1 || d > 7)) {
      throw ArgumentError('days are 1 (Mon) to 7 (Sun)');
    }
    if (!_inDay(start) || !_inDay(end)) {
      throw ArgumentError('times must be within a day');
    }
  }

  final Set<int> days;
  final int start;
  final int end;

  bool get overnight => end < start;
  bool get allDay => start == end;

  static bool _inDay(int minute) => minute >= 0 && minute < 24 * 60;

  @override
  Map<String, Object?> toJson() => {
    'type': 'every',
    'days': days.toList()..sort(),
    'start': start,
    'end': end,
  };

  @override
  bool operator ==(Object other) =>
      other is EveryPlan &&
      other.start == start &&
      other.end == end &&
      other.days.length == days.length &&
      other.days.containsAll(days);

  @override
  int get hashCode => Object.hash(start, end, Object.hashAllUnordered(days));
}

/// What happens when a blocked site or app is opened while active.
sealed class ScheduleAction {
  const ScheduleAction();

  Map<String, Object?> toJson();

  /// Throws [FormatException] for anything malformed.
  factory ScheduleAction.fromJson(Map<String, Object?> json) =>
      switch (_get<String>(json, 'type')) {
        'block' => const BlockAction(),
        'message' => MessageAction(_get<String>(json, 'text')),
        'redirect' => RedirectAction(_get<String>(json, 'package')),
        final type => throw FormatException('unknown action type $type'),
      };
}

class BlockAction extends ScheduleAction {
  const BlockAction();

  @override
  Map<String, Object?> toJson() => {'type': 'block'};

  @override
  bool operator ==(Object other) => other is BlockAction;

  @override
  int get hashCode => 0;
}

class MessageAction extends ScheduleAction {
  const MessageAction(this.text);

  final String text;

  @override
  Map<String, Object?> toJson() => {'type': 'message', 'text': text};

  @override
  bool operator ==(Object other) =>
      other is MessageAction && other.text == text;

  @override
  int get hashCode => text.hashCode;
}

class RedirectAction extends ScheduleAction {
  const RedirectAction(this.packageName);

  final String packageName;

  @override
  Map<String, Object?> toJson() => {'type': 'redirect', 'package': packageName};

  @override
  bool operator ==(Object other) =>
      other is RedirectAction && other.packageName == packageName;

  @override
  int get hashCode => packageName.hashCode;
}

DateTime _toMillis(DateTime t) => DateTime.fromMillisecondsSinceEpoch(
  t.millisecondsSinceEpoch,
  isUtc: t.isUtc,
);

T _get<T>(Map<String, Object?> json, String key) {
  final value = json[key];
  if (value is! T) throw FormatException('$key should be $T, got $value');
  return value;
}

List<String> _strings(Map<String, Object?> json, String key) => [
  for (final s in _get<List<Object?>>(json, key))
    s is String ? s : throw FormatException('$key should hold strings, got $s'),
];

bool _listEquals(List<String> a, List<String> b) {
  if (a.length != b.length) return false;
  for (var i = 0; i < a.length; i++) {
    if (a[i] != b[i]) return false;
  }
  return true;
}
