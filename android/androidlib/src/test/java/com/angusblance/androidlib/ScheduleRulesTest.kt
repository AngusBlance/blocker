package com.angusblance.androidlib

import com.angusblance.androidlib.ScheduleRules.PauseResult
import org.json.JSONArray
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertThrows
import org.junit.Test
import java.time.DayOfWeek
import java.time.DayOfWeek.MONDAY
import java.time.DayOfWeek.SATURDAY
import java.time.DayOfWeek.SUNDAY
import java.time.Instant
import java.time.LocalDateTime
import java.time.ZoneId
import java.time.ZonedDateTime

class ScheduleRulesTest {
  private val london = ZoneId.of("Europe/London")

  // 2026-10-12 is a Monday.
  private fun at(day: Int, time: String): ZonedDateTime =
    LocalDateTime.parse("2026-10-%02dT%s".format(day, time)).atZone(london)

  private fun schedule(
    id: String,
    plan: Schedule.Plan,
    domains: List<String> = listOf("youtube.com"),
  ) = Schedule(
    id = id,
    name = id,
    sites = listOf("YouTube"),
    domains = domains,
    apps = listOf("com.google.android.youtube"),
    plan = plan,
  )

  private fun every(vararg days: DayOfWeek, start: Int, end: Int) =
    Schedule.Plan.Every(days.toSet(), start, end)

  private val work = schedule("work", every(MONDAY, start = 9 * 60, end = 17 * 60))
  private val evening = schedule("evening", every(MONDAY, start = 18 * 60, end = 23 * 60))
  private val monday10 = at(12, "10:00")

  private fun json(vararg s: Schedule) = Schedule.listToJson(s.toList())

  private fun save(
    stored: String?,
    vararg incoming: Schedule,
    passwordOk: Boolean = false,
    now: ZonedDateTime = monday10,
  ) = Schedule.listFromJson(ScheduleRules.replaceAll(stored, json(*incoming), passwordOk, now))

  // Saving

  @Test
  fun `anything can change while nothing is running`() {
    val stored = json(work, evening)
    assertEquals(listOf(evening), save(stored, evening, now = at(12, "08:00")))
  }

  @Test
  fun `without the password a running schedule cannot be weakened`() {
    val stored = json(work, evening)
    val weakened = listOf(
      arrayOf(evening), // removed
      arrayOf(work.copy(enabled = false), evening),
      arrayOf(work.copy(plan = every(MONDAY, start = 9 * 60, end = 9 * 60 + 30)), evening),
      arrayOf(work.copy(action = Schedule.Action.Message("ok")), evening),
      arrayOf(work.copy(domains = emptyList()), evening),
      arrayOf(work.copy(apps = emptyList()), evening),
    )
    for (incoming in weakened) {
      assertThrows(ScheduleRules.LockedException::class.java) { save(stored, *incoming) }
    }
  }

  @Test
  fun `with the password a running schedule can change`() {
    val stored = json(work, evening)
    assertEquals(listOf(evening), save(stored, evening, passwordOk = true))
  }

  @Test
  fun `a running schedule can be strengthened, and others edited, without the password`() {
    val stored = json(work, evening)
    val more = work.copy(name = "Work!", domains = listOf("youtube.com", "netflix.com"))
    val saved = save(stored, more, evening.copy(enabled = false))
    assertEquals(listOf(more, evening.copy(enabled = false)), saved)
  }

  @Test
  fun `pauses can't be set or cleared by saving`() {
    val pausedWork = work.copy(pausedUntil = at(12, "17:00").toInstant().toEpochMilli())
    val stored = json(pausedWork, evening)
    // Trying to un-pause: the stored pause is kept.
    assertEquals(pausedWork.pausedUntil, save(stored, work, evening).first().pausedUntil)
    // Trying to pause via save: ignored.
    val sneaky = evening.copy(pausedUntil = Long.MAX_VALUE)
    assertNull(save(json(work, evening), work, sneaky, now = at(12, "08:00"))[1].pausedUntil)
  }

  @Test
  fun `duplicate ids and malformed lists are rejected`() {
    assertThrows(IllegalArgumentException::class.java) {
      save(null, work, work.copy(name = "again"))
    }
    assertThrows(IllegalArgumentException::class.java) {
      ScheduleRules.replaceAll(null, "nope", false, monday10)
    }
  }

  // Pausing

  @Test
  fun `pausing needs the password and a running schedule`() {
    val stored = json(work, evening)
    assertEquals(
      PauseResult.WRONG_PASSWORD to null,
      ScheduleRules.pause(stored, "work", false, monday10),
    )
    assertEquals(
      PauseResult.NOT_RUNNING,
      ScheduleRules.pause(stored, "evening", true, monday10).first,
    )
    assertEquals(
      PauseResult.NOT_RUNNING,
      ScheduleRules.pause(stored, "missing", true, monday10).first,
    )
  }

  @Test
  fun `pausing rewrites only that schedule and keeps unreadable entries`() {
    val stored = JSONArray(json(work, evening)).put(org.json.JSONObject().put("id", 7)).toString()
    val (result, next) = ScheduleRules.pause(stored, "work", true, monday10)
    assertEquals(PauseResult.PAUSED, result)
    val array = JSONArray(next)
    assertEquals(3, array.length())
    assertEquals(7, array.getJSONObject(2).getInt("id")) // corrupt entry kept as is
    val schedules = Schedule.listFromJsonSkippingBad(next)
    assertEquals(at(12, "17:00").toInstant().toEpochMilli(), schedules[0].pausedUntil)
    assertEquals(evening, schedules[1])
  }

  @Test
  fun `an already paused schedule isn't running, so pausing again does nothing`() {
    val (_, next) = ScheduleRules.pause(json(work), "work", true, monday10)
    assertEquals(
      PauseResult.NOT_RUNNING to null,
      ScheduleRules.pause(next, "work", true, at(12, "11:00")),
    )
  }

  @Test
  fun `pausing an all-day schedule with the next day selected brings it back at midnight`() {
    val weekend = schedule("weekend", every(SATURDAY, SUNDAY, start = 0, end = 0))
    val paused = weekend.pausedForCurrentOccurrence(at(17, "15:00"))!!
    assertEquals(at(18, "00:00").toInstant().toEpochMilli(), paused.pausedUntil)
    assert(!paused.isActive(at(17, "23:59")))
    assert(paused.isActive(at(18, "00:00")))
  }

  @Test
  fun `occurrence end in the autumn overlap is never in the past`() {
    // 2026-10-25: 01:00-02:00 happens twice in London. At the second 01:15
    // (GMT), a range ending 01:30 ends at 01:30 GMT, 15 minutes later.
    val sunday = every(SUNDAY, start = 0, end = 90)
    val secondQuarterPast = Instant.parse("2026-10-25T01:15:00Z").atZone(london)
    assertEquals(
      Instant.parse("2026-10-25T01:30:00Z"),
      sunday.occurrenceEnd(secondQuarterPast)!!.toInstant(),
    )
    val firstQuarterPast = Instant.parse("2026-10-25T00:15:00Z").atZone(london)
    assertEquals(
      Instant.parse("2026-10-25T00:30:00Z"),
      sunday.occurrenceEnd(firstQuarterPast)!!.toInstant(),
    )
  }

  // Status

  @Test
  fun `status lists running schedules with when they end`() {
    val start = at(12, "09:30").toInstant().toEpochMilli()
    val focus = schedule("focus", Schedule.Plan.For(start, start + 3_600_000))
    val status = JSONArray(ScheduleRules.status(listOf(work, evening, focus), monday10))
    assertEquals(2, status.length())
    assertEquals("work", status.getJSONObject(0).getString("id"))
    assertEquals(
      at(12, "17:00").toInstant().toEpochMilli(),
      status.getJSONObject(0).getLong("until"),
    )
    assertEquals("focus", status.getJSONObject(1).getString("id"))
    assertEquals(start + 3_600_000, status.getJSONObject(1).getLong("until"))
    val paused = work.copy(pausedUntil = at(12, "17:00").toInstant().toEpochMilli())
    assertEquals("[]", ScheduleRules.status(listOf(paused), monday10))
  }

  @Test
  fun `switching a running schedule to plain blocking needs no password`() {
    val redirecting = work.copy(action = Schedule.Action.Redirect("com.amazon.kindle"))
    val stored = json(redirecting)
    assertEquals(Schedule.Action.Block, save(stored, work)[0].action)
    assertThrows(ScheduleRules.LockedException::class.java) {
      save(stored, work.copy(action = Schedule.Action.Message("hi")))
    }
  }
}
