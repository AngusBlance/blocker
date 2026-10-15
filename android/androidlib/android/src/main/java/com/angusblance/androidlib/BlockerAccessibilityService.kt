package com.angusblance.androidlib

import android.accessibilityservice.AccessibilityService
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Handler
import android.os.Looper
import android.os.SystemClock
import android.util.Log
import android.view.accessibility.AccessibilityEvent

// Covers the screen with BlockedActivity when a blocked app comes to the
// front, or when a browser's address bar shows a blocked site. Android starts
// and keeps this running on its own once the user enables it, independent of
// the React UI.
class BlockerAccessibilityService : AccessibilityService() {
  private lateinit var store: BlockStore
  private var lastBlocked: String? = null
  private var lastBlockedAt = 0L
  private val handler = Handler(Looper.getMainLooper())

  override fun onServiceConnected() {
    store = BlockStore(this)
    Log.i(TAG, "connected")
  }

  override fun onAccessibilityEvent(event: AccessibilityEvent) {
    val packageName = event.packageName?.toString() ?: return
    if (packageName in store.blockedApps) {
      checkApp(packageName)
    } else {
      checkBrowser(packageName)
    }
  }

  private fun checkApp(packageName: String) {
    // Only when it's actually in front, not e.g. a notification it posted.
    if (rootInActiveWindow?.packageName?.toString() != packageName) return
    show(packageName, appLabel(packageName))
  }

  private fun checkBrowser(packageName: String) {
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
    UrlMatcher.matchingDomain(host, blocked) ?: return
    show(host, host, leaveBrowserPage = true)
  }

  // `key` is the host or package name; `label` is what the block screen shows.
  private fun show(key: String, label: String, leaveBrowserPage: Boolean = false) {
    // Events arrive in bursts; launch the block screen once.
    val now = SystemClock.elapsedRealtime()
    if (key == lastBlocked && now - lastBlockedAt < DEBOUNCE_MS) return
    lastBlocked = key
    lastBlockedAt = now

    Log.i(TAG, "blocking $key")
    if (leaveBrowserPage) {
      // Press Back in the browser first, so the tab leaves the blocked page
      // (or closes, if it was opened just for it). Otherwise going back into
      // the browser lands on the same page and gets blocked all over again.
      performGlobalAction(GLOBAL_ACTION_BACK)
      handler.postDelayed({ launchBlockScreen(label) }, BACK_SETTLE_MS)
    } else {
      launchBlockScreen(label)
    }
  }

  private fun launchBlockScreen(label: String) {
    startActivity(
      Intent(this, BlockedActivity::class.java)
        .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP)
        .putExtra(BlockedActivity.EXTRA_HOST, label),
    )
  }

  private fun appLabel(packageName: String): String = try {
    packageManager.getApplicationLabel(packageManager.getApplicationInfo(packageName, 0)).toString()
  } catch (e: PackageManager.NameNotFoundException) {
    packageName
  }

  override fun onInterrupt() {}

  companion object {
    const val TAG = "BlockerService"
    private const val DEBOUNCE_MS = 1500L
    private const val BACK_SETTLE_MS = 300L
  }
}
