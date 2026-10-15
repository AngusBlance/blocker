package com.angusblance.androidlib

import android.content.Context
import android.util.Base64
import java.security.SecureRandom

// Android counterpart of blocklib's /etc/hosts block + password.txt: the block
// list and unlock password live in app-private SharedPreferences, which the
// accessibility service reads directly so blocking works with the app closed.
class BlockStore(context: Context) {
  private val prefs = context.applicationContext
    .getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)

  val blockedDomains: Set<String>
    get() = prefs.getStringSet(KEY_BLOCKED, emptySet())!!.toSet()

  // Package names of apps (e.g. com.google.android.youtube) that are blocked
  // outright, whatever is on screen.
  val blockedApps: Set<String>
    get() = prefs.getStringSet(KEY_BLOCKED_APPS, emptySet())!!.toSet()

  fun block(domains: Collection<String>, apps: Collection<String>) {
    save(
      blockedDomains + domains.map(UrlMatcher::normalizeDomain),
      blockedApps + apps,
    )
  }

  // Returns false (and changes nothing) unless the typed password matches.
  fun unblock(typed: String, domains: Collection<String>, apps: Collection<String>): Boolean {
    if (typed != unlockPassword) return false
    save(
      blockedDomains - domains.map(UrlMatcher::normalizeDomain).toSet(),
      blockedApps - apps.toSet(),
    )
    return true
  }

  // Deliberately long and tedious to type out by hand - the friction is the
  // point, same as blocklib.password.generate_password.
  val unlockPassword: String
    get() = prefs.getString(KEY_PASSWORD, null) ?: generatePassword().also {
      prefs.edit().putString(KEY_PASSWORD, it).apply()
    }

  private fun save(domains: Set<String>, apps: Set<String>) {
    prefs.edit()
      .putStringSet(KEY_BLOCKED, domains)
      .putStringSet(KEY_BLOCKED_APPS, apps)
      .apply()
  }

  private fun generatePassword(): String {
    val bytes = ByteArray(96).also { SecureRandom().nextBytes(it) }
    return Base64.encodeToString(bytes, Base64.URL_SAFE or Base64.NO_PADDING or Base64.NO_WRAP)
  }

  companion object {
    const val PREFS_NAME = "androidlib.blocker"
    private const val KEY_BLOCKED = "blocked_domains"
    private const val KEY_BLOCKED_APPS = "blocked_apps"
    private const val KEY_PASSWORD = "unlock_password"
  }
}
