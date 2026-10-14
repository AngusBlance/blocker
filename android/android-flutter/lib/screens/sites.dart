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
  final void Function(Site site) requestUnlock;

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
                  '${site.domains.join(', ')} + app',
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
