package com.angusblance.androidlib

import android.content.Context
import android.util.Log

// The "Adult sites" filter. Blocked like a site, by putting ID in the
// blocked domains (manually or in a schedule); it isn't a host itself, so it
// never matches an address on its own.
//
// A site counts as adult if it's on the shipped list (assets/adult-domains.txt,
// the same list the Mac writes to /etc/hosts, from StevenBlack/hosts), or is
// one a list can't name in advance: "porn" in its host, or an adult-only
// top-level domain. No looser keywords: keyword filters block health pages
// too (Richardson et al., JAMA 2002).
class AdultSites(private val names: Set<String>) {
  fun matches(host: String): Boolean {
    val h = UrlMatcher.normalizeDomain(host)
    if ("porn" in h || h.substringAfterLast('.') in ADULT_TLDS) return true
    if (h in names) return true
    // Each parent domain too (fr.xhamster.com), except shared platforms whose
    // other subdomains are ordinary sites (the Mac only blocks the names
    // listed).
    var rest = h
    while (true) {
      val dot = rest.indexOf('.')
      if (dot < 0) return false
      rest = rest.substring(dot + 1)
      if (rest in names && rest !in SHARED_PLATFORMS) return true
    }
  }

  companion object {
    const val ID = "#adult-sites"
    private const val ASSET = "adult-domains.txt"
    private val ADULT_TLDS = setOf("xxx", "porn", "adult", "sex")
    private val SHARED_PLATFORMS = setOf("fc2.com", "2chan.net")

    fun parse(lines: Sequence<String>): AdultSites = AdultSites(
      lines.map(String::trim)
        .filter { it.isNotEmpty() && !it.startsWith("#") }
        // Hosts are matched without www. (UrlMatcher.hostOf).
        .map(UrlMatcher::normalizeDomain)
        .toHashSet(),
    )

    @Volatile private var loaded: AdultSites? = null

    // About 77,000 names: read once, on first use. Without the list it still
    // blocks by keyword and top-level domain.
    fun get(context: Context): AdultSites = loaded ?: synchronized(this) {
      loaded ?: runCatching {
        context.assets.open(ASSET).bufferedReader().useLines(::parse)
      }.getOrElse {
        Log.e(BlockerAccessibilityService.TAG, "adult list unreadable", it)
        AdultSites(emptySet())
      }.also { loaded = it }
    }
  }
}
