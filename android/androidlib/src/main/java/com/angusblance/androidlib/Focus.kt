package com.angusblance.androidlib

import org.json.JSONArray
import org.json.JSONException
import org.json.JSONObject

// Focus mode: until `endsAt`, only the allowed sites and apps can be open;
// everything else gets the block screen. The opposite of a schedule, which
// blocks a list and lets the rest through.
data class Focus(
  val endsAt: Long, // epoch millis
  // Site names as shown in the UI, plus what they resolve to.
  val sites: List<String>,
  val domains: List<String>,
  val apps: List<String>,
) {
  fun isActive(nowMs: Long) = nowMs < endsAt

  fun toJson(): JSONObject = JSONObject()
    .put("endsAt", endsAt)
    .put("sites", JSONArray(sites))
    .put("domains", JSONArray(domains))
    .put("apps", JSONArray(apps))

  companion object {
    // Strict, like Schedule.fromJson: anything malformed is an
    // IllegalArgumentException.
    fun fromJson(json: String): Focus = try {
      val o = JSONObject(json)
      // Int or Long only: org.json reads 1.5 as a BigDecimal, "1" as a String.
      val endsAt = when (val v = o.get("endsAt")) {
        is Int -> v.toLong()
        is Long -> v
        else -> throw IllegalArgumentException("endsAt should be a whole number, got $v")
      }
      Focus(endsAt, o.strings("sites"), o.strings("domains"), o.strings("apps"))
    } catch (e: JSONException) {
      throw IllegalArgumentException("malformed focus: ${e.message}", e)
    }

    private fun JSONObject.strings(key: String): List<String> {
      val array = getJSONArray(key)
      return (0 until array.length()).map {
        val v = array.get(it)
        require(v is String) { "$key must hold strings" }
        v
      }
    }
  }
}

object FocusRules {
  // Always usable during focus, whatever was picked, so the phone stays a
  // phone: the system UI and dialogs, calls and emergency calls, permission
  // and install prompts. The service adds this app, the home screen and the
  // keyboard, which it looks up on the phone.
  val SYSTEM_PACKAGES = setOf(
    "android",
    "com.android.systemui",
    "com.android.phone",
    "com.android.server.telecom",
    "com.android.emergency",
    "com.google.android.dialer",
    "com.android.dialer",
    "com.google.android.permissioncontroller",
    "com.android.permissioncontroller",
    "com.google.android.packageinstaller",
    "com.android.packageinstaller",
  )

  // How long a focus can be started for.
  const val MAX_MS = 12 * 60 * 60 * 1000L

  enum class AppVerdict { ALLOWED, CHECK_URL, BLOCKED }

  // What to do when `packageName` comes up: let it be, check the site a
  // browser shows (only allowed sites pass), or block it.
  fun appVerdict(packageName: String, focus: Focus, alwaysAllowed: Set<String>): AppVerdict = when {
    packageName in focus.apps || packageName in alwaysAllowed || packageName in SYSTEM_PACKAGES ->
      AppVerdict.ALLOWED

    BrowserUrlBars.idsFor(packageName) != null && focus.domains.isNotEmpty() -> AppVerdict.CHECK_URL

    else -> AppVerdict.BLOCKED
  }

  fun hostAllowed(host: String, focus: Focus) =
    UrlMatcher.matchingDomain(host, focus.domains) != null

  enum class EndResult { ENDED, WRONG_PASSWORD, NOT_RUNNING }

  // The focus to store when starting `json`. Refused while one is running
  // (end it first, which needs the password), or if it isn't a sensible
  // length or allows nothing.
  fun start(stored: String?, json: String, nowMs: Long): String {
    require(active(stored, nowMs) == null) { "focus is already on" }
    val focus = Focus.fromJson(json)
    require(focus.endsAt > nowMs) { "focus must end in the future" }
    require(focus.endsAt - nowMs <= MAX_MS) { "focus can last at most 12 hours" }
    require(focus.domains.isNotEmpty() || focus.apps.isNotEmpty()) {
      "allow at least one site or app"
    }
    return focus.toJson().toString()
  }

  // The running focus, or null. A corrupt one counts as none: focus blocks
  // nearly everything, so it must never get stuck on.
  fun active(stored: String?, nowMs: Long): Focus? = stored
    ?.let { runCatching { Focus.fromJson(it) }.getOrNull() }
    ?.takeIf { it.isActive(nowMs) }

  fun end(stored: String?, passwordOk: Boolean, nowMs: Long): EndResult = when {
    active(stored, nowMs) == null -> EndResult.NOT_RUNNING
    !passwordOk -> EndResult.WRONG_PASSWORD
    else -> EndResult.ENDED
  }
}
