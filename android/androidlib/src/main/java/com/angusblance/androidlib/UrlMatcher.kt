package com.angusblance.androidlib

import java.net.URI

object UrlMatcher {
  // Address bars show things like "youtube.com", "m.youtube.com/watch?v=..."
  // or "https://www.netflix.com/browse". Search terms contain spaces and
  // aren't hosts, so they return null.
  fun hostOf(addressBarText: String): String? {
    val text = addressBarText.trim()
    if (text.isEmpty() || text.any(Char::isWhitespace)) return null
    val withScheme = if ("://" in text) text else "https://$text"
    val host = try {
      URI(withScheme).host
    } catch (e: Exception) {
      null
    } ?: return null
    if ('.' !in host) return null
    return normalizeDomain(host)
  }

  fun normalizeDomain(domain: String): String =
    domain.trim().lowercase().removePrefix("www.").trimEnd('.')

  // youtube.com blocks youtube.com and any subdomain (m.youtube.com), but not
  // notyoutube.com.
  fun matchingDomain(host: String, blocked: Collection<String>): String? =
    blocked.firstOrNull { host == it || host.endsWith(".$it") }

  // Google image search is a page on google.com (udm=2, or tbm=isch in older
  // links) rather than its own host, so blocking images.google.com blocks
  // it too.
  const val GOOGLE_IMAGES = "images.google.com"
  private val googleImageSearch = Regex(
    """^(https?://)?(www\.)?google\.[a-z.]+/(imghp|search\?([^#]*&)?(udm=2|tbm=isch)(&|#|$))""",
    RegexOption.IGNORE_CASE,
  )

  fun isGoogleImageSearch(addressBarText: String): Boolean =
    googleImageSearch.containsMatchIn(addressBarText.trim())

  // What in `blocked` blocks this address: the blocked domain covering its
  // host, GOOGLE_IMAGES for an image search, or AdultSites.ID for an adult
  // site. Null if nothing does.
  fun blockedBy(
    addressBarText: String,
    blocked: Collection<String>,
    adult: () -> AdultSites,
  ): String? {
    val host = hostOf(addressBarText) ?: return null
    matchingDomain(host, blocked)?.let { return it }
    if (GOOGLE_IMAGES in blocked && isGoogleImageSearch(addressBarText)) return GOOGLE_IMAGES
    if (AdultSites.ID in blocked && adult().matches(host)) return AdultSites.ID
    return null
  }
}
