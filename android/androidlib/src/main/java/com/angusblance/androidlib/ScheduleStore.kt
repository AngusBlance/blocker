package com.angusblance.androidlib

import android.content.Context
import java.time.ZonedDateTime

// Schedules live next to BlockStore's block list in the same app-private
// SharedPreferences, as the JSON Schedule.kt and the Dart UI share. The rules
// for changing them are in ScheduleRules; this applies them to storage.
// commit() rather than apply(), so a failed write reaches the UI.
class ScheduleStore(context: Context) {
  private val blockStore = BlockStore(context)
  private val prefs = context.applicationContext
    .getSharedPreferences(BlockStore.PREFS_NAME, Context.MODE_PRIVATE)

  private val raw: String?
    get() = prefs.getString(KEY_SCHEDULES, null)

  val schedules: List<Schedule>
    get() = Schedule.listFromJsonSkippingBad(raw)

  // Replaces every schedule. A save that would weaken a running schedule
  // needs the unlock password (see ScheduleRules.replaceAll).
  fun replaceAll(json: String, password: String? = null, now: ZonedDateTime = ZonedDateTime.now()) {
    save(ScheduleRules.replaceAll(raw, json, passwordOk(password), now))
  }

  // Ends a running schedule early (decision D1): needs the unlock password and
  // pauses only the occurrence running now.
  fun pause(
    id: String,
    password: String,
    now: ZonedDateTime = ZonedDateTime.now(),
  ): ScheduleRules.PauseResult {
    val (result, next) = ScheduleRules.pause(raw, id, passwordOk(password), now)
    if (next != null) save(next)
    return result
  }

  // For the UI: which schedules are running and when each ends.
  fun statusJson(now: ZonedDateTime = ZonedDateTime.now()): String =
    ScheduleRules.status(schedules, now)

  // For the UI: the schedule that starts next.
  fun nextJson(now: ZonedDateTime = ZonedDateTime.now()): String =
    ScheduleRules.next(schedules, now)

  fun activeBlocks(now: ZonedDateTime = ZonedDateTime.now()): ActiveBlocks =
    ActiveBlocks.compute(blockStore.blockedDomains, blockStore.blockedApps, schedules, now)

  private fun save(json: String) {
    check(prefs.edit().putString(KEY_SCHEDULES, json).commit()) { "couldn't save schedules" }
  }

  private fun passwordOk(password: String?) =
    password != null && password == blockStore.unlockPassword

  companion object {
    private const val KEY_SCHEDULES = "schedules"
  }
}
