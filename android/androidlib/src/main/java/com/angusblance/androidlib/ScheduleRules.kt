package com.angusblance.androidlib

import org.json.JSONArray
import org.json.JSONException
import org.json.JSONObject
import java.time.ZonedDateTime

// The rules for changing stored schedules, as pure functions on their JSON so
// they're testable without Android. ScheduleStore applies them to
// SharedPreferences.
object ScheduleRules {
  enum class PauseResult { PAUSED, WRONG_PASSWORD, NOT_RUNNING }

  class LockedException(message: String) : IllegalStateException(message)

  // Replaces the stored list with `incomingJson`, returning the JSON to store.
  //
  // Ending a schedule early must cost the unlock password (decision D1), so
  // without `passwordOk` a save may not weaken anything running now: every
  // active schedule must still be there, still enabled, with the same plan
  // and action (or plain blocking), still blocking at least the same sites
  // and apps. Pauses are
  // only ever set by pause(), so incoming pausedUntil values are ignored and
  // the stored ones kept.
  //
  // Throws IllegalArgumentException if the incoming list is malformed and
  // LockedException if it would weaken a running schedule.
  fun replaceAll(
    storedJson: String?,
    incomingJson: String,
    passwordOk: Boolean,
    now: ZonedDateTime,
  ): String {
    val stored = Schedule.listFromJsonSkippingBad(storedJson)
    val storedById = stored.associateBy { it.id }
    val incoming = Schedule.listFromJson(incomingJson).map {
      it.copy(pausedUntil = storedById[it.id]?.pausedUntil)
    }
    if (!passwordOk) {
      val incomingById = incoming.associateBy { it.id }
      for (running in stored.filter { it.isActive(now) }) {
        val next = incomingById[running.id]
        val kept = next != null &&
          next.enabled &&
          next.plan == running.plan &&
          // Plain blocking is the strictest action, so switching to it is fine.
          (next.action == running.action || next.action == Schedule.Action.Block) &&
          next.domains.containsAll(running.domains) &&
          next.apps.containsAll(running.apps)
        if (!kept) {
          throw LockedException(
            "\"${running.name}\" is running; changing it needs the unlock password",
          )
        }
      }
    }
    return Schedule.listToJson(incoming)
  }

  // Ends schedule `id` early, if it's running: pauses just the occurrence
  // running now. Returns the result and, if paused, the JSON to store. Only
  // that schedule's entry is rewritten; anything else stored, even entries
  // too corrupt to parse, is kept as it was.
  fun pause(
    storedJson: String?,
    id: String,
    passwordOk: Boolean,
    now: ZonedDateTime,
  ): Pair<PauseResult, String?> {
    if (!passwordOk) return PauseResult.WRONG_PASSWORD to null
    val array = try {
      JSONArray(storedJson ?: "[]")
    } catch (e: JSONException) {
      return PauseResult.NOT_RUNNING to null
    }
    for (i in 0 until array.length()) {
      val schedule = try {
        Schedule.fromJson(array.getJSONObject(i))
      } catch (e: IllegalArgumentException) {
        continue
      } catch (e: JSONException) {
        continue
      }
      if (schedule.id != id) continue
      val paused =
        schedule.pausedForCurrentOccurrence(now) ?: return PauseResult.NOT_RUNNING to null
      array.put(i, paused.toJson())
      return PauseResult.PAUSED to array.toString()
    }
    return PauseResult.NOT_RUNNING to null
  }

  // Each running schedule's id and when its current occurrence ends, as JSON
  // [{"id": "...", "until": epochMillis}], in list order.
  fun status(schedules: List<Schedule>, now: ZonedDateTime): String = JSONArray(
    schedules.mapNotNull { s ->
      s.activeUntil(now)?.let { JSONObject().put("id", s.id).put("until", it) }
    },
  ).toString()

  // The schedule that starts soonest after `now` among those not running,
  // as JSON {"id": "...", "at": epochMillis}, or "null" if none.
  fun next(schedules: List<Schedule>, now: ZonedDateTime): String {
    val soonest = schedules
      .filter { !it.isActive(now) }
      .mapNotNull { s -> s.nextStart(now)?.let { s to it } }
      .minByOrNull { it.second.toInstant() }
      ?: return "null"
    return JSONObject().put(
      "id",
      soonest.first.id,
    ).put("at", soonest.second.toInstant().toEpochMilli()).toString()
  }
}
