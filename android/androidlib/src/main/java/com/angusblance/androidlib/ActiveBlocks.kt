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
