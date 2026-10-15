package com.angusblance.androidlib

import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import java.time.DayOfWeek
import java.time.DayOfWeek.FRIDAY
import java.time.DayOfWeek.MONDAY
import java.time.DayOfWeek.SATURDAY
import java.time.DayOfWeek.SUNDAY
import java.time.LocalDateTime
import java.time.ZoneId
import java.time.ZonedDateTime

class ScheduleNextTest {
  private val london = ZoneId.of("Europe/London")

  // 2026-10-12 is a Monday.
  private fun at(day: Int, time: String): ZonedDateTime =
    LocalDateTime.parse("2026-10-%02dT%s".format(day, time)).atZone(london)

  private fun every(id: String, vararg days: DayOfWeek, start: Int, end: Int) = Schedule(
    id = id,
    name = id,
    sites = emptyList(),
    domains = listOf("youtube.com"),
    apps = emptyList(),
    plan = Schedule.Plan.Every(days.toSet(), start, end),
  )

  private val work = every("work", MONDAY, FRIDAY, start = 540, end = 1020)

  @Test
  fun `next start is later today, or the next selected day`() {
    assertEquals(at(12, "09:00"), work.nextStart(at(12, "08:00")))
    assertEquals(at(16, "09:00"), work.nextStart(at(12, "10:00"))) // Mon passed → Fri
    assertEquals(at(19, "09:00"), work.nextStart(at(16, "12:00"))) // Fri → next Mon
  }

  @Test
  fun `all-day schedules start at midnight`() {
    val sat = every("sat", SATURDAY, start = 0, end = 0)
    assertEquals(at(17, "00:00"), sat.nextStart(at(12, "10:00")))
  }

  @Test
  fun `a pause skips the starts it covers, and disabled never starts`() {
    val paused = work.copy(pausedUntil = at(16, "17:00").toInstant().toEpochMilli())
    assertEquals(at(19, "09:00"), paused.nextStart(at(12, "10:00")))
    assertNull(work.copy(enabled = false).nextStart(at(12, "08:00")))
  }

  @Test
  fun `one-off blocks start once`() {
    val start = at(12, "15:00").toInstant().toEpochMilli()
    val focus = work.copy(plan = Schedule.Plan.For(start, start + 3_600_000))
    assertEquals(at(12, "15:00"), focus.nextStart(at(12, "10:00")))
    assertNull(focus.nextStart(at(12, "15:30")))
  }

  @Test
  fun `next picks the soonest schedule that isn't already running`() {
    val evening = every("evening", MONDAY, start = 18 * 60, end = 23 * 60)
    val json = JSONObject(ScheduleRules.next(listOf(work, evening), at(12, "10:00")))
    assertEquals("evening", json.getString("id")) // work is running now
    assertEquals(at(12, "18:00").toInstant().toEpochMilli(), json.getLong("at"))
    assertEquals("null", ScheduleRules.next(emptyList(), at(12, "10:00")))
  }

  @Test
  fun `a schedule ended early is next again at its following occurrence`() {
    val now = at(12, "10:00")
    val paused = work.pausedForCurrentOccurrence(now)!!
    assertEquals(at(16, "09:00"), paused.nextStart(now))
    assertEquals("work", JSONObject(ScheduleRules.next(listOf(paused), now)).getString("id"))
  }

  @Test
  fun `editing a paused schedule to run past the pause starts it when the pause ends`() {
    val now = at(12, "10:00")
    val paused = work.pausedForCurrentOccurrence(now)!! // until 17:00
    val longer = paused.copy(plan = Schedule.Plan.Every(setOf(MONDAY, FRIDAY), 540, 1080))
    assertEquals(at(12, "17:00"), longer.nextStart(now))
  }

  @Test
  fun `overnight and all-day plans, and a paused all-day day`() {
    val night = every("night", MONDAY, start = 22 * 60, end = 7 * 60)
    assertEquals(at(19, "22:00"), night.nextStart(at(13, "03:00"))) // inside Monday's night
    val weekend = every("weekend", SATURDAY, SUNDAY, start = 0, end = 0)
    val sat = at(17, "10:00")
    val paused = weekend.pausedForCurrentOccurrence(sat)!! // until Sunday 00:00
    assertEquals(at(18, "00:00"), paused.nextStart(sat))
  }

  @Test
  fun `a one-off ended early never starts again`() {
    val start = at(12, "10:00").toInstant().toEpochMilli()
    val focus = work.copy(plan = Schedule.Plan.For(start, start + 3_600_000))
    val ended = focus.pausedForCurrentOccurrence(at(12, "10:30"))!!
    assertNull(ended.nextStart(at(12, "10:30")))
  }

  @Test
  fun `a start in the spring-forward gap begins when the clocks jump`() {
    val early = every("early", SUNDAY, start = 90, end = 300) // 01:30–05:00
    val jump = LocalDateTime.parse("2027-03-28T02:00").atZone(london) // 01:00 GMT
    assertEquals(jump, early.nextStart(LocalDateTime.parse("2027-03-27T12:00").atZone(london)))
    assertTrue(early.isActive(jump))
  }
}
