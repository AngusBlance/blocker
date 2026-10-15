package com.angusblance.androidlib

import org.json.JSONArray
import org.json.JSONObject
import java.time.DayOfWeek
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
    return when (plan) {
      is Plan.For -> now.toInstant().toEpochMilli().let { it >= plan.startsAt && it < plan.endsAt }
      is Plan.Every -> plan.covers(now)
    }
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

  companion object {
    fun fromJson(json: JSONObject): Schedule = Schedule(
      id = json.getString("id"),
      name = json.getString("name"),
      sites = json.getJSONArray("sites").strings(),
      domains = json.getJSONArray("domains").strings(),
      apps = json.getJSONArray("apps").strings(),
      plan = planFrom(json.getJSONObject("plan")),
      action = actionFrom(json.getJSONObject("action")),
      enabled = json.optBoolean("enabled", true),
    )

    fun listToJson(schedules: List<Schedule>): String = JSONArray(
      schedules.map {
        it.toJson()
      },
    ).toString()

    fun listFromJson(text: String): List<Schedule> {
      val array = JSONArray(text)
      return (0 until array.length()).map { fromJson(array.getJSONObject(it)) }
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

    private fun planFrom(json: JSONObject): Plan = when (val type = json.getString("type")) {
      "for" -> Plan.For(json.getLong("startsAt"), json.getLong("endsAt"))

      "every" -> {
        val days = json.getJSONArray("days")
        Plan.Every(
          days = (0 until days.length()).map { DayOfWeek.of(days.getInt(it)) }.toSet(),
          start = json.getInt("start"),
          end = json.getInt("end"),
        )
      }

      else -> throw IllegalArgumentException("unknown plan type $type")
    }

    private fun actionJson(action: Action): JSONObject = when (action) {
      Action.Block -> JSONObject().put("type", "block")
      is Action.Message -> JSONObject().put("type", "message").put("text", action.text)
      is Action.Redirect -> JSONObject().put("type", "redirect").put("package", action.packageName)
    }

    private fun actionFrom(json: JSONObject): Action = when (val type = json.getString("type")) {
      "block" -> Action.Block
      "message" -> Action.Message(json.getString("text"))
      "redirect" -> Action.Redirect(json.getString("package"))
      else -> throw IllegalArgumentException("unknown action type $type")
    }

    private fun JSONArray.strings(): List<String> = (0 until length()).map { getString(it) }
  }
}
