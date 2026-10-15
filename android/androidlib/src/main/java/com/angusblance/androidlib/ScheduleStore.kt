package com.angusblance.androidlib

import android.content.Context
import java.time.ZonedDateTime

// Schedules live next to BlockStore's block list in the same app-private
// SharedPreferences, as the JSON Schedule.kt and the Dart UI share.
class ScheduleStore(context: Context) {
  private val blockStore = BlockStore(context)
  private val prefs = context.applicationContext
    .getSharedPreferences(BlockStore.PREFS_NAME, Context.MODE_PRIVATE)

  val schedules: List<Schedule>
    get() = Schedule.listFromJsonSkippingBad(prefs.getString(KEY_SCHEDULES, null))

  // Replaces every schedule. Strict: a malformed list from the UI is an
  // IllegalArgumentException and nothing is saved.
  fun replaceAll(json: String) {
    val parsed = Schedule.listFromJson(json)
    prefs.edit().putString(KEY_SCHEDULES, Schedule.listToJson(parsed)).apply()
  }

  // Ends a running schedule early (decision D1): needs the unlock password and
  // pauses only the occurrence running now. False if the password is wrong or
  // the schedule isn't running.
  fun pause(id: String, typedPassword: String, now: ZonedDateTime = ZonedDateTime.now()): Boolean {
    if (typedPassword != blockStore.unlockPassword) return false
    val all = schedules
    val paused = all.find { it.id == id }?.pausedForCurrentOccurrence(now) ?: return false
    prefs.edit()
      .putString(KEY_SCHEDULES, Schedule.listToJson(all.map { if (it.id == id) paused else it }))
      .apply()
    return true
  }

  fun activeBlocks(now: ZonedDateTime = ZonedDateTime.now()): ActiveBlocks =
    ActiveBlocks.compute(blockStore.blockedDomains, blockStore.blockedApps, schedules, now)

  companion object {
    private const val KEY_SCHEDULES = "schedules"
  }
}
