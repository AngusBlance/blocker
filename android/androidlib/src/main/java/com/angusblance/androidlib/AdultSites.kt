package com.angusblance.androidlib

import android.content.Context

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
    // The host and each parent domain: m.pornhub.com, pornhub.com.
    var rest = h
    while (true) {
      if (rest in names) return true
      val dot = rest.indexOf('.')
      if (dot < 0) return false
      rest = rest.substring(dot + 1)
    }
  }

  companion object {
    const val ID = "#adult-sites"
    private const val ASSET = "adult-domains.txt"
    private val ADULT_TLDS = setOf("xxx", "porn", "adult", "sex")

    fun parse(lines: Sequence<String>): AdultSites = AdultSites(
      lines.map { it.trim().lowercase() }
        .filter { it.isNotEmpty() && !it.startsWith("#") }
        .toHashSet(),
    )

    @Volatile private var loaded: AdultSites? = null

    // About 77,000 names: read once, on first use.
    fun get(context: Context): AdultSites = loaded ?: synchronized(this) {
      loaded ?: context.assets.open(ASSET).bufferedReader().useLines(::parse)
        .also { loaded = it }
    }
  }
}
