package com.angusblance.androidlib

import android.content.Context

// Keeps the focus session next to the blocks and schedules.
class FocusStore(context: Context) {
  private val blockStore = BlockStore(context)
  private val prefs = context.applicationContext
    .getSharedPreferences(BlockStore.PREFS_NAME, Context.MODE_PRIVATE)

  private val raw: String?
    get() = prefs.getString(KEY_FOCUS, null)

  fun active(nowMs: Long = System.currentTimeMillis()): Focus? = FocusRules.active(raw, nowMs)

  fun start(json: String, nowMs: Long = System.currentTimeMillis()) {
    save(FocusRules.start(raw, json, nowMs))
  }

  // Ending early needs the unlock password, like ending a schedule early.
  fun end(password: String, nowMs: Long = System.currentTimeMillis()): FocusRules.EndResult {
    val result = FocusRules.end(raw, password == blockStore.unlockPassword, nowMs)
    if (result == FocusRules.EndResult.ENDED) {
      check(prefs.edit().remove(KEY_FOCUS).commit()) { "couldn't end focus" }
    }
    return result
  }

  private fun save(json: String) {
    check(prefs.edit().putString(KEY_FOCUS, json).commit()) { "couldn't save focus" }
  }

  companion object {
    private const val KEY_FOCUS = "focus"
  }
}
