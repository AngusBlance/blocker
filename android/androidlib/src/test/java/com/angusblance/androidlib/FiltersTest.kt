package com.angusblance.androidlib

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.File

class FiltersTest {
  private val adult = AdultSites.parse(
    sequenceOf("# header", "", "Pornhub.com", "example-adult.net", "www.only-www.com", "fc2.com"),
  )

  private fun blockedBy(address: String, vararg blocked: String) =
    UrlMatcher.blockedBy(address, blocked.toList()) { adult }

  @Test fun googleImageSearchIsRecognised() {
    for (url in listOf(
      "google.com/search?q=dogs&udm=2",
      "https://www.google.co.uk/search?q=x&tbm=isch&sa=X",
      "www.google.com/imghp?hl=en",
      "google.com/search?udm=2",
    )) {
      assertTrue(url, UrlMatcher.isGoogleImageSearch(url))
    }
    for (url in listOf(
      "google.com/search?q=dogs",
      "google.com/search?q=udm=2",
      "google.com/search?q=dogs&udm=28",
      "docs.google.com/search?udm=2",
      "notgoogle.com/search?udm=2",
      "udm=2 google",
    )) {
      assertFalse(url, UrlMatcher.isGoogleImageSearch(url))
    }
  }

  @Test fun googleImagesBlocksImageSearchButNotWebSearch() {
    val images = UrlMatcher.GOOGLE_IMAGES
    assertEquals(images, blockedBy("google.com/search?q=dogs&udm=2", images))
    assertEquals(images, blockedBy("images.google.com", images))
    assertNull(blockedBy("google.com/search?q=dogs", images))
    assertNull(blockedBy("google.com/search?q=dogs&udm=2", "youtube.com"))
  }

  @Test fun adultFilterUsesListParentsKeywordAndTlds() {
    assertTrue(adult.matches("pornhub.com"))
    assertTrue(adult.matches("www.example-adult.net"))
    assertTrue(adult.matches("cdn.m.example-adult.net"))
    assertTrue(adult.matches("someporntube.io"))
    assertTrue(adult.matches("anything.xxx"))
    assertTrue(adult.matches("site.sex"))
    assertFalse(adult.matches("essex.ac.uk"))
    assertFalse(adult.matches("adult-education.org"))
    assertFalse(adult.matches("xxxlutz.de"))
    assertFalse(adult.matches("net"))
  }

  @Test fun wwwOnlyEntriesStillMatch() {
    // Address bars are matched without www., so the list is too.
    assertTrue(adult.matches(UrlMatcher.hostOf("https://www.only-www.com/")!!))
    assertTrue(adult.matches("only-www.com"))
  }

  @Test fun sharedPlatformsBlockOnlyTheNameListed() {
    assertTrue(adult.matches("fc2.com"))
    assertFalse(adult.matches("someone.blog.fc2.com"))
  }

  @Test fun adultFilterOnlyBlocksWhenSwitchedOn() {
    assertEquals(AdultSites.ID, blockedBy("https://www.example-adult.net/x", AdultSites.ID))
    assertNull(blockedBy("https://www.example-adult.net/x", "youtube.com"))
    assertNull(blockedBy("wikipedia.org", AdultSites.ID))
  }

  @Test fun plainDomainsStillWinAndTheIdIsNeverAHost() {
    assertEquals("youtube.com", blockedBy("m.youtube.com/watch", "youtube.com", AdultSites.ID))
    assertNull(blockedBy("adult-sites", AdultSites.ID))
    assertNull(UrlMatcher.matchingDomain("x.com", listOf(AdultSites.ID)))
  }

  @Test fun shippedListLoads() {
    // The asset is a link to blocklib's list; tests run from the app module.
    val file = File("../../../androidlib/src/main/assets/adult-domains.txt")
    val sites = file.bufferedReader().useLines(AdultSites::parse)
    assertTrue(sites.matches("xvideos.com"))
    assertTrue(sites.matches("fr.xhamster.com"))
    assertFalse(sites.matches("google.com"))
    assertFalse(sites.matches("reddit.com"))
  }

  @Test fun schedulesCoverFiltersByListingThem() {
    val s = Schedule(
      id = "s",
      name = "nights",
      sites = listOf("Adult sites"),
      domains = listOf(AdultSites.ID, UrlMatcher.GOOGLE_IMAGES),
      apps = emptyList(),
      plan = Schedule.Plan.Every(java.time.DayOfWeek.values().toSet(), 0, 60),
      action = Schedule.Action.Message("bed"),
    )
    val blocks = ActiveBlocks(setOf(AdultSites.ID), emptySet(), listOf(s))
    assertEquals(s, blocks.scheduleFor(host = AdultSites.ID))
    assertEquals(s, blocks.scheduleFor(host = UrlMatcher.GOOGLE_IMAGES))
    assertNull(blocks.scheduleFor(host = "www.google.com"))
  }
}
