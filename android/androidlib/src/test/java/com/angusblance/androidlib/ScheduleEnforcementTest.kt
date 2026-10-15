package com.angusblance.androidlib

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import java.time.DayOfWeek
import java.time.DayOfWeek.MONDAY
import java.time.DayOfWeek.SATURDAY
import java.time.DayOfWeek.SUNDAY
import java.time.Instant
import java.time.LocalDateTime
import java.time.ZoneId
import java.time.ZonedDateTime

class ScheduleEnforcementTest {
  private val london = ZoneId.of("Europe/London")

  // 2026-10-12 is a Monday.
  private fun at(day: Int, time: String): ZonedDateTime =
    LocalDateTime.parse("2026-10-%02dT%s".format(day, time)).atZone(london)

  private fun schedule(
    id: String,
    plan: Schedule.Plan,
    domains: List<String> = listOf("youtube.com"),
    apps: List<String> = listOf("com.google.android.youtube"),
    enabled: Boolean = true,
  ) = Schedule(
    id = id,
    name = id,
    sites = listOf("YouTube"),
    domains = domains,
    apps = apps,
    plan = plan,
    enabled = enabled,
  )

  private fun every(vararg days: DayOfWeek, start: Int, end: Int) =
    Schedule.Plan.Every(days.toSet(), start, end)

  private val work = schedule("work", every(MONDAY, start = 9 * 60, end = 17 * 60))

  @Test
  fun `active schedules add their sites to the manual block list`() {
    val blocks = ActiveBlocks.compute(
      manualDomains = setOf("netflix.com"),
      manualApps = setOf("com.netflix.mediaclient"),
      schedules = listOf(work),
      now = at(12, "10:00"),
    )
    assertEquals(setOf("netflix.com", "youtube.com"), blocks.domains)
    assertEquals(setOf("com.netflix.mediaclient", "com.google.android.youtube"), blocks.apps)
    assertEquals(listOf(work), blocks.schedules)
  }

  @Test
  fun `inactive, disabled and paused schedules add nothing`() {
    val off = work.copy(enabled = false)
    val paused = work.copy(pausedUntil = at(12, "17:00").toInstant().toEpochMilli())
    for (now in listOf(at(12, "08:00"), at(12, "10:00"))) {
      val schedules = if (now.hour == 8) listOf(work) else listOf(off, paused)
      val blocks = ActiveBlocks.compute(setOf("netflix.com"), emptySet(), schedules, now)
      assertEquals(setOf("netflix.com"), blocks.domains)
      assertTrue(blocks.apps.isEmpty())
      assertTrue(blocks.schedules.isEmpty())
    }
  }

  @Test
  fun `schedules never loosen a manual block`() {
    // Stacking (D2): the same site blocked manually and by a schedule that
    // isn't running stays blocked.
    val blocks = ActiveBlocks.compute(
      setOf("youtube.com"),
      emptySet(),
      listOf(work),
      at(12, "20:00"),
    )
    assertEquals(setOf("youtube.com"), blocks.domains)
  }

  @Test
  fun `schedule domains are normalised like manual ones`() {
    val messy =
      schedule("messy", every(MONDAY, start = 0, end = 0), domains = listOf("  WWW.YouTube.com. "))
    val blocks = ActiveBlocks.compute(emptySet(), emptySet(), listOf(messy), at(12, "10:00"))
    assertEquals(setOf("youtube.com"), blocks.domains)
  }

  @Test
  fun `occurrence end for daytime, overnight and all-day ranges`() {
    assertEquals(
      at(12, "17:00"),
      every(MONDAY, start = 540, end = 1020).occurrenceEnd(at(12, "10:00")),
    )
    val bedtime = every(MONDAY, SUNDAY, start = 22 * 60, end = 7 * 60)
    assertEquals(at(13, "07:00"), bedtime.occurrenceEnd(at(12, "23:00"))) // evening part
    assertEquals(at(12, "07:00"), bedtime.occurrenceEnd(at(12, "03:00"))) // morning, from Sunday
    assertEquals(
      at(18, "00:00"),
      every(SATURDAY, start = 0, end = 0).occurrenceEnd(at(17, "15:00")),
    )
    assertNull(every(MONDAY, start = 540, end = 1020).occurrenceEnd(at(12, "18:00")))
  }

  @Test
  fun `occurrence end lands on the real clock time across a DST change`() {
    // 2026-10-25 04:00 London is GMT, an hour later in UTC than in summer.
    val end = every(
      SUNDAY,
      start = 0,
      end = 4 * 60,
    ).occurrenceEnd(Instant.parse("2026-10-25T00:30:00Z").atZone(london))
    assertEquals(Instant.parse("2026-10-25T04:00:00Z"), end!!.toInstant())
  }

  @Test
  fun `ending early pauses only the running occurrence`() {
    val paused = work.pausedForCurrentOccurrence(at(12, "10:00"))!!
    assertEquals(at(12, "17:00").toInstant().toEpochMilli(), paused.pausedUntil)
    assertFalse(paused.isActive(at(12, "16:59")))
    assertTrue(paused.isActive(at(19, "10:00"))) // next Monday it's back
    assertNull(work.pausedForCurrentOccurrence(at(12, "18:00"))) // not running
  }

  @Test
  fun `ending a one-off block early ends it`() {
    val start = at(15, "12:00").toInstant().toEpochMilli()
    val focus = schedule("focus", Schedule.Plan.For(start, start + 3_600_000))
    val paused = focus.pausedForCurrentOccurrence(at(15, "12:30"))!!
    assertEquals(start + 3_600_000, paused.pausedUntil)
    assertFalse(paused.isActive(at(15, "12:31")))
  }

  @Test
  fun `the service's lenient parse skips only the bad schedules`() {
    val good = Schedule.listToJson(listOf(work))
    val mixed =
      good.dropLast(1) + """,{"id":1},{"id":"x","name":"x","sites":[],"domains":[],"apps":[],""" +
        """"plan":{"type":"every","days":[9],"start":0,"end":0},"action":{"type":"block"}}]"""
    assertEquals(listOf(work), Schedule.listFromJsonSkippingBad(mixed))
    assertEquals(emptyList<Schedule>(), Schedule.listFromJsonSkippingBad("not json"))
    assertEquals(emptyList<Schedule>(), Schedule.listFromJsonSkippingBad(null))
    assertEquals(emptyList<Schedule>(), Schedule.listFromJsonSkippingBad(""))
  }
}
