package com.angusblance.androidlib

import com.angusblance.androidlib.Schedule.Action
import org.junit.Assert.assertEquals
import org.junit.Test
import java.time.DayOfWeek
import java.time.LocalDateTime
import java.time.ZoneId

class ScheduleActionsTest {
  // A Monday morning.
  private val now = LocalDateTime.parse("2026-10-12T10:00").atZone(ZoneId.of("Europe/London"))

  private fun schedule(
    id: String,
    action: Action,
    domains: List<String>,
    apps: List<String> = emptyList(),
  ) = Schedule(
    id = id,
    name = id,
    sites = emptyList(),
    domains = domains,
    apps = apps,
    plan = Schedule.Plan.Every(DayOfWeek.values().toSet(), 0, 0),
    action = action,
  )

  private val bed =
    schedule(
      "bed",
      Action.Message("go to bed"),
      listOf("youtube.com"),
      listOf("com.google.android.youtube"),
    )
  private val kindle =
    schedule("kindle", Action.Redirect("com.amazon.kindle"), listOf("youtube.com", "tiktok.com"))
  private val plain = schedule("plain", Action.Block, listOf("youtube.com", "netflix.com"))

  private fun blocks(vararg s: Schedule, manualDomains: Set<String> = emptySet()) =
    ActiveBlocks.compute(manualDomains, emptySet(), s.toList(), now)

  @Test
  fun `the first running schedule with a non-plain action wins, in list order`() {
    assertEquals(
      Action.Message("go to bed"),
      blocks(plain, bed, kindle).actionFor(host = "youtube.com"),
    )
    assertEquals(
      Action.Redirect("com.amazon.kindle"),
      blocks(plain, kindle, bed).actionFor(host = "youtube.com"),
    )
  }

  @Test
  fun `subdomains and apps match their schedule`() {
    assertEquals(Action.Message("go to bed"), blocks(bed).actionFor(host = "m.youtube.com"))
    assertEquals(
      Action.Message("go to bed"),
      blocks(bed).actionFor(app = "com.google.android.youtube"),
    )
    assertEquals(
      Action.Redirect("com.amazon.kindle"),
      blocks(kindle).actionFor(host = "www.tiktok.com"),
    )
  }

  @Test
  fun `plain blocks, manual blocks and other sites just block`() {
    assertEquals(Action.Block, blocks(plain, bed).actionFor(host = "netflix.com"))
    assertEquals(
      Action.Block,
      blocks(bed, manualDomains = setOf("crunchyroll.com")).actionFor(host = "crunchyroll.com"),
    )
    assertEquals(Action.Block, blocks(kindle).actionFor(app = "com.netflix.mediaclient"))
  }

  @Test
  fun `schedules that aren't running don't lend their action`() {
    val off = bed.copy(enabled = false)
    assertEquals(Action.Block, blocks(off, plain).actionFor(host = "youtube.com"))
  }

  @Test
  fun `block and message show the block screen, with the message if any`() {
    assertEquals(
      BlockResponse.BlockScreen("youtube.com"),
      BlockResponse.decide(Action.Block, "youtube.com") {
        true
      },
    )
    assertEquals(
      BlockResponse.BlockScreen("youtube.com", "go to bed"),
      BlockResponse.decide(Action.Message("  go to bed "), "youtube.com") { true },
    )
    assertEquals(
      BlockResponse.BlockScreen("x"),
      BlockResponse.decide(Action.Message("   "), "x") {
        true
      },
    )
  }

  @Test
  fun `redirect opens the app, but blocks if it's missing or is the blocked app itself`() {
    val toKindle = Action.Redirect("com.amazon.kindle")
    assertEquals(
      BlockResponse.OpenApp("com.amazon.kindle"),
      BlockResponse.decide(toKindle, "TikTok") {
        true
      },
    )
    assertEquals(
      BlockResponse.BlockScreen("TikTok"),
      BlockResponse.decide(toKindle, "TikTok") {
        false
      },
    )
    assertEquals(
      BlockResponse.BlockScreen("Kindle"),
      BlockResponse.decide(toKindle, "Kindle", blockedApp = "com.amazon.kindle") { true },
    )
  }
}
