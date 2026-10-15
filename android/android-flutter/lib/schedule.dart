/// A block that applies at certain times. The UI creates and edits these and
/// hands them to androidlib as JSON; androidlib's Schedule.kt decides when one
/// is active, since the accessibility service enforces it. The JSON format
/// must match Schedule.kt (both are tested against the same fixture).
class Schedule {
  const Schedule({
    required this.id,
    required this.name,
    required this.sites,
    required this.domains,
    required this.apps,
    required this.plan,
    this.action = const BlockAction(),
    this.enabled = true,
  });

  final String id;
  final String name;

  /// Site names as shown in the UI, plus what they resolve to.
  final List<String> sites;
  final List<String> domains;
  final List<String> apps;
  final SchedulePlan plan;
  final ScheduleAction action;
  final bool enabled;

  Schedule copyWith({
    String? name,
    SchedulePlan? plan,
    ScheduleAction? action,
    bool? enabled,
  }) => Schedule(
    id: id,
    name: name ?? this.name,
    sites: sites,
    domains: domains,
    apps: apps,
    plan: plan ?? this.plan,
    action: action ?? this.action,
    enabled: enabled ?? this.enabled,
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
  };

  factory Schedule.fromJson(Map<String, Object?> json) => Schedule(
    id: json['id']! as String,
    name: json['name']! as String,
    sites: _strings(json['sites']),
    domains: _strings(json['domains']),
    apps: _strings(json['apps']),
    plan: SchedulePlan.fromJson(json['plan']! as Map<String, Object?>),
    action: ScheduleAction.fromJson(json['action']! as Map<String, Object?>),
    enabled: json['enabled'] as bool? ?? true,
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
      other.enabled == enabled;

  @override
  int get hashCode => Object.hash(id, name, plan, action, enabled);
}

sealed class SchedulePlan {
  const SchedulePlan();

  Map<String, Object?> toJson();

  factory SchedulePlan.fromJson(Map<String, Object?> json) =>
      switch (json['type']) {
        'for' => ForPlan(
          startsAt: DateTime.fromMillisecondsSinceEpoch(
            json['startsAt']! as int,
          ),
          endsAt: DateTime.fromMillisecondsSinceEpoch(json['endsAt']! as int),
        ),
        'every' => EveryPlan(
          days: {for (final d in json['days']! as List) d as int},
          start: json['start']! as int,
          end: json['end']! as int,
        ),
        final type => throw ArgumentError('unknown plan type $type'),
      };
}

/// "Block now for…": from [startsAt] until [endsAt].
class ForPlan extends SchedulePlan {
  ForPlan({required this.startsAt, required this.endsAt}) {
    if (!endsAt.isAfter(startsAt)) {
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
  EveryPlan({required this.days, required this.start, required this.end}) {
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

  factory ScheduleAction.fromJson(Map<String, Object?> json) =>
      switch (json['type']) {
        'block' => const BlockAction(),
        'message' => MessageAction(json['text']! as String),
        'redirect' => RedirectAction(json['package']! as String),
        final type => throw ArgumentError('unknown action type $type'),
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

List<String> _strings(Object? list) => [
  for (final s in list! as List) s as String,
];

bool _listEquals(List<String> a, List<String> b) {
  if (a.length != b.length) return false;
  for (var i = 0; i < a.length; i++) {
    if (a[i] != b[i]) return false;
  }
  return true;
}
