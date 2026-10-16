import 'package:flutter/material.dart';

import '../blocker.dart';
import '../sites.dart';
import '../theme.dart';
import '../ui.dart';

class SitesScreen extends StatelessWidget {
  const SitesScreen({
    super.key,
    required this.blocker,
    required this.requestUnlock,
  });

  final Blocker blocker;

  /// Opens the unlock screen for [site], or for everything blocked if null.
  final void Function(Site? site) requestUnlock;

  @override
  Widget build(BuildContext context) {
    return Pane(
      title: 'Blocked sites',
      focused: true,
      children: [
        Muted('${sites.length} sites, ${blocker.blockedSites.length} blocked'),
        Column(
          children: [
            for (final site in sites)
              _SiteRow(
                site: site,
                on: blocker.isBlocked(site),
                onTap: () => blocker.isBlocked(site)
                    ? requestUnlock(site)
                    : blocker.block([site]),
              ),
          ],
        ),
        const Muted('tap to block. unblocking needs the password.'),
        if (blocker.blockedSites.length > 1)
          AppButton(
            'unlock everything',
            key: const Key('unlock-everything'),
            onPressed: () => requestUnlock(null),
          ),
      ],
    );
  }
}

class _SiteRow extends StatelessWidget {
  const _SiteRow({required this.site, required this.on, required this.onTap});

  final Site site;
  final bool on;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) => InkWell(
    key: Key('site-${site.name}'),
    onTap: onTap,
    child: Container(
      padding: const EdgeInsets.symmetric(vertical: 12),
      decoration: const BoxDecoration(
        border: Border(bottom: BorderSide(color: AppColors.border)),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            on ? '(x)' : '( )',
            style: monoStyle(
              color: on ? AppColors.accent : AppColors.muted,
              bold: on,
            ),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(site.name, style: monoStyle()),
                Text(
                  site.detail,
                  style: monoStyle(color: AppColors.muted, size: 12),
                ),
              ],
            ),
          ),
        ],
      ),
    ),
  );
}
