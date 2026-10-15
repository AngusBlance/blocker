package com.angusblance.androidlib

import java.time.ZonedDateTime

// What's blocked right now: the manual block list plus every active
// schedule's sites. Blocking only ever adds up (decision D2), so starting a
// schedule never loosens anything already blocked.
data class ActiveBlocks(
  val domains: Set<String>,
  val apps: Set<String>,
  val schedules: List<Schedule>,
) {
  // What to do about a blocked site (`host`) or app (`app`): the action of
  // the first running schedule covering it, in list order, that does more
  // than plain blocking; otherwise just block (manual blocks always just
  // block). Decision D2.
  fun actionFor(host: String? = null, app: String? = null): Schedule.Action {
    for (s in schedules) {
      if (s.action == Schedule.Action.Block) continue
      val covers = (app != null && app in s.apps) ||
        (
          host != null &&
            UrlMatcher.matchingDomain(host, s.domains.map(UrlMatcher::normalizeDomain)) != null
          )
      if (covers) return s.action
    }
    return Schedule.Action.Block
  }

  companion object {
    fun compute(
      manualDomains: Set<String>,
      manualApps: Set<String>,
      schedules: List<Schedule>,
      now: ZonedDateTime,
    ): ActiveBlocks {
      val active = schedules.filter { it.isActive(now) }
      return ActiveBlocks(
        domains = manualDomains + active.flatMap { it.domains }.map(UrlMatcher::normalizeDomain),
        apps = manualApps + active.flatMap { it.apps },
        schedules = active,
      )
    }
  }
}
