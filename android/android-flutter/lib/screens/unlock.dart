import 'package:flutter/material.dart';

import '../blocker.dart';
import '../sites.dart';
import '../ui.dart';
import 'password_entry.dart';

/// Unblocks one site (or everything blocked) after the unlock password is
/// typed out.
class UnlockScreen extends StatefulWidget {
  const UnlockScreen({
    super.key,
    required this.blocker,
    required this.site,
    required this.done,
  });

  final Blocker blocker;

  /// The site to unlock, or null to unlock everything that's blocked.
  final Site? site;
  final VoidCallback done;

  @override
  State<UnlockScreen> createState() => _UnlockScreenState();
}

class _UnlockScreenState extends State<UnlockScreen> {
  String? _password;

  @override
  void initState() {
    super.initState();
    widget.blocker.backend.unlockPassword().then((p) {
      if (mounted) setState(() => _password = p);
    });
  }

  List<Site> get _targets =>
      widget.site != null ? [widget.site!] : widget.blocker.blockedSites;

  @override
  Widget build(BuildContext context) {
    if (_targets.isEmpty) {
      return const Pane(
        title: 'Unlock',
        children: [Muted('nothing is blocked right now.')],
      );
    }
    return PasswordEntry(
      password: _password ?? '',
      title: widget.site != null
          ? 'Unlock ${widget.site!.name}'
          : 'Unlock everything',
      explanation:
          'type the password below to unlock. paste is off on purpose.',
      actionLabel: 'unlock',
      onCancel: widget.site != null ? widget.done : null,
      onSubmit: (typed) async {
        final ok = await widget.blocker.unblock(typed, _targets);
        if (ok) widget.done();
        return ok;
      },
    );
  }
}
