package com.angusblance.androidlib

// Browser package -> view ids of its address bar. Browsers rename these
// between versions, so this list is the part that needs maintaining.
object BrowserUrlBars {
  private val ids = mapOf(
    "com.android.chrome" to listOf("com.android.chrome:id/url_bar"),
    "com.chrome.beta" to listOf("com.chrome.beta:id/url_bar"),
    "com.brave.browser" to listOf("com.brave.browser:id/url_bar"),
    "com.microsoft.emmx" to listOf("com.microsoft.emmx:id/url_bar"),
    "org.mozilla.firefox" to listOf(
      "org.mozilla.firefox:id/mozac_browser_toolbar_url_view",
      "org.mozilla.firefox:id/url_bar_title",
    ),
    "com.sec.android.app.sbrowser" to listOf(
      "com.sec.android.app.sbrowser:id/location_bar_edit_text",
    ),
    "com.opera.browser" to listOf("com.opera.browser:id/url_field"),
    "com.duckduckgo.mobile.android" to listOf(
      "com.duckduckgo.mobile.android:id/omnibarTextInput",
    ),
  )

  fun idsFor(packageName: String): List<String>? = ids[packageName]
}
