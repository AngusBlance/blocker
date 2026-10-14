package com.angusblance.androidlib

import android.accessibilityservice.AccessibilityService
import android.content.Intent
import android.os.SystemClock
import android.util.Log
import android.view.accessibility.AccessibilityEvent

// Watches browser address bars and covers the browser with BlockedActivity
// when the current site is on the block list. Android starts and keeps this
// running on its own once the user enables it, independent of the React UI.
class BlockerAccessibilityService : AccessibilityService() {
  private lateinit var store: BlockStore
  private var lastBlockedHost: String? = null
  private var lastBlockedAt = 0L

  override fun onServiceConnected() {
    store = BlockStore(this)
    Log.i(TAG, "connected")
  }

  override fun onAccessibilityEvent(event: AccessibilityEvent) {
    val packageName = event.packageName?.toString() ?: return
    val barIds = BrowserUrlBars.idsFor(packageName) ?: return
    val blocked = store.blockedDomains
    if (blocked.isEmpty()) return

    val root = rootInActiveWindow ?: return
    val bar = barIds.firstNotNullOfOrNull { id ->
      root.findAccessibilityNodeInfosByViewId(id).firstOrNull()
    } ?: return

    // While the user is typing, the bar holds a half-finished address.
    if (bar.isFocused) return

    val host = UrlMatcher.hostOf(bar.text?.toString() ?: return) ?: return
    val match = UrlMatcher.matchingDomain(host, blocked) ?: return
    block(host, match)
  }

  private fun block(host: String, matchedDomain: String) {
    // Content-changed events arrive in bursts; launch the block screen once.
    val now = SystemClock.elapsedRealtime()
    if (host == lastBlockedHost && now - lastBlockedAt < DEBOUNCE_MS) return
    lastBlockedHost = host
    lastBlockedAt = now

    Log.i(TAG, "blocking $host (matched $matchedDomain)")
    startActivity(
      Intent(this, BlockedActivity::class.java)
        .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP)
        .putExtra(BlockedActivity.EXTRA_HOST, host)
    )
  }

  override fun onInterrupt() {}

  companion object {
    const val TAG = "BlockerService"
    private const val DEBOUNCE_MS = 1500L
  }
}
