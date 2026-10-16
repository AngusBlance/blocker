package com.angusblance.androidlib

import com.angusblance.androidlib.FocusRules.AppVerdict
import com.angusblance.androidlib.FocusRules.EndResult
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertThrows
import org.junit.Assert.assertTrue
import org.junit.Test

class FocusTest {
  private val now = 1_760_000_000_000L
  private val hour = 3_600_000L
  private val focus = Focus(
    endsAt = now + hour,
    sites = listOf("YouTube"),
    domains = listOf("youtube.com", "googlevideo.com"),
    apps = listOf("com.google.android.youtube", "com.notion.android"),
  )
  private val launcher = "com.google.android.apps.nexuslauncher"

  @Test
  fun `allowed apps, this app, home and the system stay usable`() {
    assertEquals(
      AppVerdict.ALLOWED,
      FocusRules.appVerdict("com.notion.android", focus, setOf(launcher)),
    )
    assertEquals(AppVerdict.ALLOWED, FocusRules.appVerdict(launcher, focus, setOf(launcher)))
    assertEquals(
      AppVerdict.ALLOWED,
      FocusRules.appVerdict("com.android.systemui", focus, emptySet()),
    )
    assertEquals(
      AppVerdict.ALLOWED,
      FocusRules.appVerdict("com.google.android.dialer", focus, emptySet()),
    )
  }

  @Test
  fun `everything else is blocked, settings included`() {
    assertEquals(
      AppVerdict.BLOCKED,
      FocusRules.appVerdict("com.netflix.mediaclient", focus, setOf(launcher)),
    )
    assertEquals(
      AppVerdict.BLOCKED,
      FocusRules.appVerdict("com.android.settings", focus, setOf(launcher)),
    )
  }

  @Test
  fun `browsers only show allowed sites, and are blocked if no site is allowed`() {
    assertEquals(
      AppVerdict.CHECK_URL,
      FocusRules.appVerdict("com.android.chrome", focus, emptySet()),
    )
    assertTrue(FocusRules.hostAllowed("m.youtube.com", focus))
    assertTrue(FocusRules.hostAllowed("rr1.googlevideo.com", focus))
    assertFalse(FocusRules.hostAllowed("netflix.com", focus))
    assertFalse(FocusRules.hostAllowed("notyoutube.com", focus))
    val appsOnly = focus.copy(sites = emptyList(), domains = emptyList())
    assertEquals(
      AppVerdict.BLOCKED,
      FocusRules.appVerdict("com.android.chrome", appsOnly, emptySet()),
    )
    // Picking the browser itself allows all of it.
    val withChrome = focus.copy(apps = focus.apps + "com.android.chrome")
    assertEquals(
      AppVerdict.ALLOWED,
      FocusRules.appVerdict("com.android.chrome", withChrome, emptySet()),
    )
  }

  @Test
  fun `starting checks length, contents and that none is running`() {
    val json = focus.toJson().toString()
    val stored = FocusRules.start(null, json, now)
    assertEquals(focus, Focus.fromJson(stored))
    assertThrows(IllegalArgumentException::class.java) { FocusRules.start(stored, json, now) }
    // A finished one doesn't count.
    val later = focus.copy(endsAt = now + 3 * hour).toJson().toString()
    assertEquals(later, FocusRules.start(stored, later, now + 2 * hour))
    val past = focus.copy(endsAt = now - 1).toJson().toString()
    assertThrows(IllegalArgumentException::class.java) { FocusRules.start(null, past, now) }
    val long = focus.copy(endsAt = now + 13 * hour).toJson().toString()
    assertThrows(IllegalArgumentException::class.java) { FocusRules.start(null, long, now) }
    val nothing = focus.copy(domains = emptyList(), apps = emptyList()).toJson().toString()
    assertThrows(IllegalArgumentException::class.java) { FocusRules.start(null, nothing, now) }
  }

  @Test
  fun `a finished or corrupt focus is no focus`() {
    val stored = focus.toJson().toString()
    assertEquals(focus, FocusRules.active(stored, now))
    assertNull(FocusRules.active(stored, now + hour))
    assertNull(FocusRules.active("{broken", now))
    assertNull(FocusRules.active(null, now))
  }

  @Test
  fun `ending early needs the password`() {
    val stored = focus.toJson().toString()
    assertEquals(EndResult.WRONG_PASSWORD, FocusRules.end(stored, false, now))
    assertEquals(EndResult.ENDED, FocusRules.end(stored, true, now))
    assertEquals(EndResult.NOT_RUNNING, FocusRules.end(stored, true, now + hour))
  }

  @Test
  fun `json is strict`() {
    assertThrows(IllegalArgumentException::class.java) {
      Focus.fromJson("""{"endsAt":1.5,"sites":[],"domains":[],"apps":[]}""")
    }
    assertThrows(IllegalArgumentException::class.java) {
      Focus.fromJson("""{"endsAt":"1","sites":[],"domains":[],"apps":[]}""")
    }
    assertThrows(IllegalArgumentException::class.java) {
      Focus.fromJson("""{"endsAt":1,"sites":[1],"domains":[],"apps":[]}""")
    }
    assertThrows(IllegalArgumentException::class.java) { Focus.fromJson("""{"endsAt":1}""") }
  }
}
