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
  fun `redirect opens the app, but blocks if it's missing or is the app in front`() {
    val toKindle = Action.Redirect("com.amazon.kindle")
    assertEquals(
      BlockResponse.OpenApp("com.amazon.kindle", "TikTok", "Read instead"),
      BlockResponse.decide(toKindle, "TikTok", "Read instead") { true },
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

  @Test
  fun `redirecting a site to the browser it's open in blocks instead`() {
    val toChrome = Action.Redirect("com.android.chrome")
    assertEquals(
      BlockResponse.BlockScreen("youtube.com"),
      BlockResponse.decide(toChrome, "youtube.com", blockedApp = "com.android.chrome") { true },
    )
  }

  @Test
  fun `two schedules redirecting to each other can't bounce forever`() {
    // TikTok -> Instagram and Instagram -> TikTok: the target is blocked too,
    // so each shows the block screen instead of opening the other.
    val toInsta =
      schedule(
        "a",
        Action.Redirect("com.instagram.android"),
        emptyList(),
        listOf("com.zhiliaoapp.musically"),
      )
    val toTikTok =
      schedule(
        "b",
        Action.Redirect("com.zhiliaoapp.musically"),
        emptyList(),
        listOf("com.instagram.android"),
      )
    val blocks = blocks(toInsta, toTikTok)
    for (app in listOf("com.zhiliaoapp.musically", "com.instagram.android")) {
      val s = blocks.scheduleFor(app = app)!!
      val response = BlockResponse.decide(s.action, app, s.name, app, {
        it in blocks.apps
      }) { true }
      assertEquals(BlockResponse.BlockScreen(app), response)
    }
  }

  @Test
  fun `long messages are cut short`() {
    val long = "x".repeat(500)
    val response = BlockResponse.decide(Action.Message(long), "x") {
      true
    } as BlockResponse.BlockScreen
    assertEquals(BlockResponse.MAX_MESSAGE, response.message!!.length)
    assertEquals('…', response.message!!.last())
  }

  @Test
  fun `the schedule whose action applies is found, for the explanation`() {
    assertEquals("kindle", blocks(plain, kindle).scheduleFor(host = "tiktok.com")!!.id)
    assertEquals(null, blocks(plain).scheduleFor(host = "youtube.com"))
  }
}
