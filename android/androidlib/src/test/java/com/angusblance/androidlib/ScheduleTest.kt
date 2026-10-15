package com.angusblance.androidlib

import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertThrows
import org.junit.Assert.assertTrue
import org.junit.Test
import java.time.DayOfWeek.FRIDAY
import java.time.DayOfWeek.MONDAY
import java.time.DayOfWeek.SATURDAY
import java.time.DayOfWeek.SUNDAY
import java.time.Instant
import java.time.LocalDateTime
import java.time.ZoneId
import java.time.ZonedDateTime

class ScheduleTest {
  private val london = ZoneId.of("Europe/London")

  // 2026-10-12 is a Monday.
  private fun at(day: Int, time: String): ZonedDateTime =
    LocalDateTime.parse("2026-10-%02dT%s".format(day, time)).atZone(london)

  private fun utc(instant: String): ZonedDateTime = Instant.parse(instant).atZone(london)

  private val fixtureText: String by lazy {
    javaClass.classLoader!!.getResource("schedules.json")!!.readText()
  }

  private val fixture: List<Schedule> by lazy { Schedule.listFromJson(fixtureText) }

  private fun fixture(id: String) = fixture.single { it.id == id }

  // JSON as plain Kotlin values, keeping types (Int vs Double vs String), so
  // two documents compare equal only if they say exactly the same thing.
  private fun plain(value: Any?): Any? = when (value) {
    is JSONObject -> value.keys().asSequence().associateWith { plain(value.get(it)) }
    is JSONArray -> (0 until value.length()).map { plain(value.get(it)) }
    else -> value
  }

  private fun every(vararg days: java.time.DayOfWeek, start: Int, end: Int) = Schedule(
    id = "t",
    name = "t",
    sites = emptyList(),
    domains = emptyList(),
    apps = emptyList(),
    plan = Schedule.Plan.Every(days.toSet(), start, end),
  )

  @Test
  fun `weekday range is active from start up to but not including end`() {
    val work = fixture("work") // Mon-Fri 09:00-17:00
    assertFalse(work.isActive(at(12, "08:59")))
    assertTrue(work.isActive(at(12, "09:00")))
    assertTrue(work.isActive(at(12, "16:59")))
    assertFalse(work.isActive(at(12, "17:00")))
    assertTrue(work.isActive(at(16, "12:00"))) // Friday
    assertFalse(work.isActive(at(17, "12:00"))) // Saturday
  }

  @Test
  fun `overnight range belongs to the day it starts on`() {
    val bedtime = fixture("bedtime") // Sun-Thu 22:00-07:00
    assertTrue(bedtime.isActive(at(12, "23:00"))) // Monday night
    assertTrue(bedtime.isActive(at(13, "06:59"))) // Tuesday morning, from Monday
    assertFalse(bedtime.isActive(at(13, "07:00")))
    assertTrue(bedtime.isActive(at(12, "06:00"))) // Monday morning, from Sunday
    assertFalse(bedtime.isActive(at(16, "23:00"))) // Friday not selected
    assertFalse(bedtime.isActive(at(17, "06:00"))) // so Saturday morning is free
    assertFalse(bedtime.isActive(at(12, "21:59")))
  }

  @Test
  fun `start equal to end means the whole day`() {
    val weekend = fixture("weekend").copy(enabled = true) // Sat+Sun, 00:00-00:00
    assertTrue(weekend.isActive(at(17, "00:00")))
    assertTrue(weekend.isActive(at(18, "23:59")))
    assertFalse(weekend.isActive(at(16, "23:59")))
    assertFalse(weekend.isActive(at(19, "00:00")))
  }

  @Test
  fun `disabled schedules are never active`() {
    val weekend = fixture("weekend")
    assertFalse(weekend.enabled)
    assertFalse(weekend.isActive(at(17, "12:00")))
    assertFalse(fixture("work").copy(enabled = false).isActive(at(12, "12:00")))
  }

  @Test
  fun `for plan runs from startsAt until endsAt`() {
    val focus = fixture("focus") // 1760000000000 .. +1h
    val start = Instant.ofEpochMilli(1760000000000).atZone(london)
    assertFalse(focus.isActive(start.minusNanos(1_000_000)))
    assertTrue(focus.isActive(start))
    assertTrue(focus.isActive(start.plusMinutes(59)))
    assertFalse(focus.isActive(start.plusHours(1)))
  }

  @Test
  fun `spring forward skips the missing hour without breaking`() {
    // 2026-03-29: London clocks go 01:00 GMT -> 02:00 BST.
    val sunday = every(SUNDAY, start = 90, end = 150) // 01:30-02:30
    assertFalse(sunday.isActive(utc("2026-03-29T00:59:00Z"))) // 00:59 GMT
    assertTrue(sunday.isActive(utc("2026-03-29T01:00:00Z"))) // 02:00 BST
    assertFalse(sunday.isActive(utc("2026-03-29T01:30:00Z"))) // 02:30 BST
  }

  @Test
  fun `fall back covers the repeated hour both times`() {
    // 2026-10-25: London clocks go 02:00 BST -> 01:00 GMT, so 01:xx happens twice.
    val sunday = every(SUNDAY, start = 60, end = 120) // 01:00-02:00
    assertTrue(sunday.isActive(utc("2026-10-25T00:30:00Z"))) // 01:30 BST
    assertTrue(sunday.isActive(utc("2026-10-25T01:30:00Z"))) // 01:30 GMT
    assertFalse(sunday.isActive(utc("2026-10-25T02:00:00Z"))) // 02:00 GMT
  }

  @Test
  fun `invalid plans are rejected`() {
    assertThrows(IllegalArgumentException::class.java) { Schedule.Plan.Every(emptySet(), 0, 60) }
    assertThrows(IllegalArgumentException::class.java) {
      Schedule.Plan.Every(
        setOf(MONDAY),
        0,
        24 * 60,
      )
    }
    assertThrows(IllegalArgumentException::class.java) {
      Schedule.Plan.Every(setOf(MONDAY), -1, 60)
    }
    assertThrows(IllegalArgumentException::class.java) { Schedule.Plan.For(100, 100) }
  }

  @Test
  fun `fixture parses into every plan and action type`() {
    assertEquals(listOf("work", "bedtime", "focus", "weekend"), fixture.map { it.id })
    assertEquals(Schedule.Plan.Every(setOf(SATURDAY, SUNDAY), 0, 0), fixture("weekend").plan)
    assertEquals(Schedule.Action.Message("go to bed"), fixture("bedtime").action)
    assertEquals(Schedule.Action.Redirect("com.amazon.kindle"), fixture("focus").action)
    assertEquals(Schedule.Action.Block, fixture("work").action)
    assertEquals(listOf("youtube.com", "googlevideo.com"), fixture("work").domains)
  }

  @Test
  fun `json round trips`() {
    assertEquals(fixture, Schedule.listFromJson(Schedule.listToJson(fixture)))
  }

  @Test
  fun `unknown plan or action types are rejected`() {
    val json = fixture("work").toJson()
    json.put("plan", JSONObject().put("type", "sometimes"))
    assertThrows(IllegalArgumentException::class.java) { Schedule.fromJson(json) }
    val json2 = fixture("work").toJson().put("action", JSONObject().put("type", "explode"))
    assertThrows(IllegalArgumentException::class.java) { Schedule.fromJson(json2) }
  }

  @Test
  fun `friday only overnight does not leak into sunday`() {
    val friday = every(FRIDAY, start = 22 * 60, end = 2 * 60)
    assertTrue(friday.isActive(at(17, "01:00"))) // Saturday early hours
    assertFalse(friday.isActive(at(18, "01:00"))) // Sunday early hours
  }

  @Test
  fun `writes exactly the fixture's JSON, types included`() {
    // Dart reads what this writes: a number written as a string or a double
    // would break the app even if it round trips here.
    assertEquals(plain(JSONArray(fixtureText)), plain(JSONArray(Schedule.listToJson(fixture))))
  }

  @Test
  fun `paused schedules are off until pausedUntil, then back`() {
    val monday9 = at(12, "09:00")
    val work = fixture("work").copy(pausedUntil = at(12, "17:00").toInstant().toEpochMilli())
    assertFalse(work.isActive(monday9))
    assertTrue(work.isActive(at(13, "09:00"))) // Tuesday: paused only Monday's occurrence
    // The fixture's pause is long past, so it changes nothing.
    assertTrue(fixture("work").isActive(monday9))
  }

  @Test
  fun `malformed values are rejected as IllegalArgumentException`() {
    fun rejects(change: (JSONObject) -> Unit) {
      val json = JSONObject(fixture("work").toJson().toString())
      change(json)
      assertThrows(IllegalArgumentException::class.java) { Schedule.fromJson(json) }
    }
    rejects { it.put("id", 123) }
    rejects { it.put("name", JSONObject.NULL) }
    rejects { it.remove("domains") }
    rejects { it.put("apps", JSONArray(listOf(1, 2))) }
    rejects { it.put("enabled", "yes") }
    rejects { it.put("pausedUntil", "soon") }
    rejects { it.getJSONObject("plan").put("start", 540.5) }
    rejects { it.getJSONObject("plan").put("start", "540") }
    rejects { it.getJSONObject("plan").put("days", JSONArray(listOf(8))) }
    rejects { it.getJSONObject("plan").put("days", JSONArray(listOf(0))) }
    rejects { it.put("plan", "every") }
    assertThrows(IllegalArgumentException::class.java) { Schedule.listFromJson("not json") }
  }
}
