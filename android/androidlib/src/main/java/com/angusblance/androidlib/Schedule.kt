package com.angusblance.androidlib

import org.json.JSONArray
import org.json.JSONException
import org.json.JSONObject
import java.time.DayOfWeek
import java.time.Instant
import java.time.LocalDateTime
import java.time.ZoneId
import java.time.ZonedDateTime

// A block that applies at certain times: either once ("block now for an
// hour") or every week on chosen days between two times. The Dart UI stores
// these as JSON; this is the only place that decides when one is active, since
// the accessibility service is what enforces it.
data class Schedule(
  val id: String,
  val name: String,
  // Site names as shown in the UI, plus what they resolve to.
  val sites: List<String>,
  val domains: List<String>,
  val apps: List<String>,
  val plan: Plan,
  val action: Action = Action.Block,
  val enabled: Boolean = true,
  // Ended early (with the unlock password) until this time, epoch millis. For
  // an "every" schedule that's the end of the current occurrence, so it comes
  // back next time; for a "for" schedule it's simply its end.
  val pausedUntil: Long? = null,
) {
  sealed interface Plan {
    // Block now for a while: active from startsAt (inclusive) to endsAt
    // (exclusive), both epoch milliseconds.
    data class For(val startsAt: Long, val endsAt: Long) : Plan {
      init {
        require(endsAt > startsAt) { "endsAt must be after startsAt" }
      }
    }

    // Every selected day from `start` to `end`, in minutes after local
    // midnight. end < start runs overnight into the next day and belongs to
    // the day it started on. start == end means the whole day.
    data class Every(val days: Set<DayOfWeek>, val start: Int, val end: Int) : Plan {
      init {
        require(days.isNotEmpty()) { "pick at least one day" }
        require(start in MINUTES && end in MINUTES) { "times must be within a day" }
      }

      fun covers(now: ZonedDateTime): Boolean {
        val minute = now.hour * 60 + now.minute
        val today = now.dayOfWeek
        return when {
          start == end -> today in days
          start < end -> today in days && minute >= start && minute < end
          else -> (today in days && minute >= start) || (today.minus(1) in days && minute < end)
        }
      }

      // When the occurrence covering `now` ends, or null if none does.
      fun occurrenceEnd(now: ZonedDateTime): ZonedDateTime? {
        if (!covers(now)) return null
        val today = now.toLocalDate()
        val minute = now.hour * 60 + now.minute
        val endsAt = when {
          start == end -> today.plusDays(1).atStartOfDay()

          start < end -> today.atTime(end / 60, end % 60)

          // Overnight: the evening part ends tomorrow, the morning part today.
          minute >= start -> today.plusDays(1).atTime(end / 60, end % 60)

          else -> today.atTime(end / 60, end % 60)
        }
        // An end skipped by a spring-forward gap is when the clocks jump;
        // covers() is already false from then.
        now.zone.rules.getTransition(endsAt)?.takeIf { it.isGap }?.let {
          return it.instant.atZone(now.zone)
        }
        // In the autumn overlap a clock time happens twice; prefer the offset
        // in force now, and take the later one if that would already be past.
        val zoned = ZonedDateTime.ofLocal(endsAt, now.zone, now.offset)
        return if (zoned.isAfter(now)) zoned else zoned.withLaterOffsetAtOverlap()
      }

      companion object {
        private val MINUTES = 0 until 24 * 60
      }
    }
  }

  // What happens when a blocked site or app is opened while this is active.
  sealed interface Action {
    data object Block : Action

    data class Message(val text: String) : Action

    data class Redirect(val packageName: String) : Action
  }

  fun isActive(now: ZonedDateTime): Boolean {
    if (!enabled) return false
    if (pausedUntil != null && now.toInstant().toEpochMilli() < pausedUntil) return false
    return when (plan) {
      is Plan.For -> now.toInstant().toEpochMilli().let { it >= plan.startsAt && it < plan.endsAt }
      is Plan.Every -> plan.covers(now)
    }
  }

  // Ending early (D1): pauses just the occurrence running now, so an "every"
  // schedule comes back next time. Null if it isn't active.
  fun pausedForCurrentOccurrence(now: ZonedDateTime): Schedule? =
    activeUntil(now)?.let { copy(pausedUntil = it) }

  // When the occurrence running now ends (epoch millis), or null if inactive.
  fun activeUntil(now: ZonedDateTime): Long? {
    if (!isActive(now)) return null
    return when (plan) {
      is Plan.For -> plan.endsAt
      is Plan.Every -> plan.occurrenceEnd(now)!!.toInstant().toEpochMilli()
    }
  }

  // When this schedule next starts after `now` (and isn't paused then), for
  // "next up" on the dashboard. Null if disabled or it never starts again.
  fun nextStart(now: ZonedDateTime): ZonedDateTime? {
    if (!enabled) return null
    val paused = pausedUntil?.let { Instant.ofEpochMilli(it) }
    fun usable(t: ZonedDateTime) =
      t.isAfter(now) && (paused == null || !t.toInstant().isBefore(paused))
    // A pause can end partway through an occurrence if the schedule was edited
    // after being ended early; it blocks again from then.
    val resumes = paused?.atZone(now.zone)?.takeIf {
      it.isAfter(now) && copy(pausedUntil = null).isActive(it)
    }
    val scheduled = when (plan) {
      is Plan.For -> Instant.ofEpochMilli(plan.startsAt).atZone(now.zone).takeIf { usable(it) }

      is Plan.Every -> (0..14).asSequence()
        .map { now.toLocalDate().plusDays(it.toLong()) }
        .filter { it.dayOfWeek in plan.days }
        .map { day -> startOf(day.atTime(plan.start / 60, plan.start % 60), now.zone) }
        .firstOrNull { usable(it) }
    }
    return listOfNotNull(resumes, scheduled).minByOrNull { it.toInstant() }
  }

  fun toJson(): JSONObject = JSONObject()
    .put("id", id)
    .put("name", name)
    .put("sites", JSONArray(sites))
    .put("domains", JSONArray(domains))
    .put("apps", JSONArray(apps))
    .put("plan", planJson(plan))
    .put("action", actionJson(action))
    .put("enabled", enabled)
    .apply { pausedUntil?.let { put("pausedUntil", it) } }

  companion object {
    // A start time that falls in a spring-forward gap begins when the clocks
    // jump (covers() is already true then), not a gap's length later.
    internal fun startOf(local: LocalDateTime, zone: ZoneId): ZonedDateTime =
      zone.rules.getTransition(local)?.takeIf { it.isGap }?.instant?.atZone(zone)
        ?: ZonedDateTime.of(local, zone)

    // Strict on types: Android's built-in org.json would otherwise turn a
    // number into "123" or null into "null" without complaint. Anything
    // malformed is an IllegalArgumentException, so callers (the accessibility
    // service) can skip one bad schedule without crashing.
    fun fromJson(json: JSONObject): Schedule = try {
      Schedule(
        id = json.str("id"),
        name = json.str("name"),
        sites = json.strings("sites"),
        domains = json.strings("domains"),
        apps = json.strings("apps"),
        plan = planFrom(json.obj("plan")),
        action = actionFrom(json.obj("action")),
        enabled = if (json.has("enabled")) json.bool("enabled") else true,
        pausedUntil = if (json.has("pausedUntil")) json.long("pausedUntil") else null,
      )
    } catch (e: JSONException) {
      throw IllegalArgumentException("malformed schedule: ${e.message}", e)
    }

    fun listToJson(schedules: List<Schedule>): String = JSONArray(
      schedules.map {
        it.toJson()
      },
    ).toString()

    // For the accessibility service: one corrupt schedule is skipped, not
    // allowed to take every other schedule down with it.
    fun listFromJsonSkippingBad(text: String?): List<Schedule> {
      if (text.isNullOrBlank()) return emptyList()
      val array = try {
        JSONArray(text)
      } catch (e: JSONException) {
        return emptyList()
      }
      return (0 until array.length()).mapNotNull { i ->
        try {
          fromJson(array.getJSONObject(i))
        } catch (e: IllegalArgumentException) {
          null
        } catch (e: JSONException) {
          null
        }
      }
    }

    fun listFromJson(text: String): List<Schedule> = try {
      val array = JSONArray(text)
      val list = (0 until array.length()).map { fromJson(array.getJSONObject(it)) }
      val duplicates = list.groupingBy { it.id }.eachCount().filterValues { it > 1 }.keys
      require(duplicates.isEmpty()) { "duplicate schedule ids: $duplicates" }
      list
    } catch (e: JSONException) {
      throw IllegalArgumentException("malformed schedule list: ${e.message}", e)
    }

    // Days are ISO numbers: 1 = Monday … 7 = Sunday.
    private fun planJson(plan: Plan): JSONObject = when (plan) {
      is Plan.For -> JSONObject()
        .put("type", "for")
        .put("startsAt", plan.startsAt)
        .put("endsAt", plan.endsAt)

      is Plan.Every -> JSONObject()
        .put("type", "every")
        .put("days", JSONArray(plan.days.map { it.value }.sorted()))
        .put("start", plan.start)
        .put("end", plan.end)
    }

    private fun planFrom(json: JSONObject): Plan = when (val type = json.str("type")) {
      "for" -> Plan.For(json.long("startsAt"), json.long("endsAt"))

      "every" -> {
        val days = json.array("days")
        Plan.Every(
          days = (0 until days.length()).map { i ->
            val day = days.get(i)
            require(day is Int && day in 1..7) { "days are 1 (Mon) to 7 (Sun), got $day" }
            DayOfWeek.of(day)
          }.toSet(),
          start = json.int("start"),
          end = json.int("end"),
        )
      }

      else -> throw IllegalArgumentException("unknown plan type $type")
    }

    private fun actionJson(action: Action): JSONObject = when (action) {
      Action.Block -> JSONObject().put("type", "block")
      is Action.Message -> JSONObject().put("type", "message").put("text", action.text)
      is Action.Redirect -> JSONObject().put("type", "redirect").put("package", action.packageName)
    }

    private fun actionFrom(json: JSONObject): Action = when (val type = json.str("type")) {
      "block" -> Action.Block
      "message" -> Action.Message(json.str("text"))
      "redirect" -> Action.Redirect(json.str("package"))
      else -> throw IllegalArgumentException("unknown action type $type")
    }

    private inline fun <reified T> JSONObject.typed(key: String): T {
      val value = if (has(key)) get(key) else null
      require(value is T) { "$key should be ${T::class.simpleName}, got $value" }
      return value
    }

    private fun JSONObject.str(key: String): String = typed(key)

    private fun JSONObject.bool(key: String): Boolean = typed(key)

    private fun JSONObject.obj(key: String): JSONObject = typed(key)

    private fun JSONObject.array(key: String): JSONArray = typed(key)

    // Whole numbers only: 540.0 or "540" is a malformed file, not a time.
    private fun JSONObject.long(key: String): Long =
      when (val value = if (has(key)) get(key) else null) {
        is Int -> value.toLong()
        is Long -> value
        else -> throw IllegalArgumentException("$key should be a whole number, got $value")
      }

    private fun JSONObject.int(key: String): Int {
      val value = long(key)
      require(value in Int.MIN_VALUE..Int.MAX_VALUE) { "$key out of range: $value" }
      return value.toInt()
    }

    private fun JSONObject.strings(key: String): List<String> {
      val array = array(key)
      return (0 until array.length()).map { i ->
        val value = array.get(i)
        require(value is String) { "$key[$i] should be a string, got $value" }
        value
      }
    }
  }
}
