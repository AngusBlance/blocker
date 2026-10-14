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
}
