package com.angusblance.androidlib

import android.accessibilityservice.AccessibilityService
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Handler
import android.os.Looper
import android.os.SystemClock
import android.util.Log
import android.view.accessibility.AccessibilityEvent
import android.widget.Toast
import java.time.ZonedDateTime

// Covers the screen with BlockedActivity when a blocked app comes to the
// front, or when a browser's address bar shows a blocked site. Android starts
// and keeps this running on its own once the user enables it, independent of
// the Flutter UI.
class BlockerAccessibilityService : AccessibilityService() {
  private lateinit var store: ScheduleStore
  private lateinit var manual: BlockStore
  private var lastBlocked: String? = null
  private var lastBlockedAt = 0L
  private val handler = Handler(Looper.getMainLooper())

  override fun onServiceConnected() {
    store = ScheduleStore(this)
    manual = BlockStore(this)
    Log.i(TAG, "connected")
  }

  override fun onAccessibilityEvent(event: AccessibilityEvent) {
    val packageName = event.packageName?.toString() ?: return
    // Manual blocks plus whatever schedules are running right now, worked out
    // per event so a schedule starts or ends without anything having to wake
    // the service up.
    // Never let a schedule problem take the service down: fall back to the
    // manual block list.
    val blocks = runCatching { store.activeBlocks() }.getOrElse {
      Log.e(TAG, "schedules unreadable, using manual blocks only", it)
      ActiveBlocks.compute(
        manual.blockedDomains,
        manual.blockedApps,
        emptyList(),
        ZonedDateTime.now(),
      )
    }
    if (packageName in blocks.apps) {
      checkApp(packageName, blocks)
    } else {
      checkBrowser(packageName, blocks)
    }
  }

  private fun checkApp(packageName: String, blocks: ActiveBlocks) {
    // Only when it's actually in front, not e.g. a notification it posted.
    if (rootInActiveWindow?.packageName?.toString() != packageName) return
    show(
      packageName,
      appLabel(packageName),
      blocks,
      blocks.scheduleFor(app = packageName),
      packageName,
    )
  }

  private fun checkBrowser(packageName: String, blocks: ActiveBlocks) {
    val barIds = BrowserUrlBars.idsFor(packageName) ?: return
    val blocked = blocks.domains
    if (blocked.isEmpty()) return

    val root = rootInActiveWindow ?: return
    val bar = barIds.firstNotNullOfOrNull { id ->
      root.findAccessibilityNodeInfosByViewId(id).firstOrNull()
    } ?: return

    // While the user is typing, the bar holds a half-finished address.
    if (bar.isFocused) return

    val host = UrlMatcher.hostOf(bar.text?.toString() ?: return) ?: return
    UrlMatcher.matchingDomain(host, blocked) ?: return
    show(host, host, blocks, blocks.scheduleFor(host = host), packageName, leaveBrowserPage = true)
  }

  // `key` is the host or package name; `label` is what the block screen shows.
  // `inFront` is the blocked app, or the browser a blocked site is open in.
  private fun show(
    key: String,
    label: String,
    blocks: ActiveBlocks,
    schedule: Schedule?,
    inFront: String,
    leaveBrowserPage: Boolean = false,
  ) {
    // Events arrive in bursts; launch the block screen once.
    val now = SystemClock.elapsedRealtime()
    if (key == lastBlocked && now - lastBlockedAt < DEBOUNCE_MS) return
    lastBlocked = key
    lastBlockedAt = now

    Log.i(TAG, "blocking $key")
    val response = BlockResponse.decide(
      action = schedule?.action ?: Schedule.Action.Block,
      label = label,
      scheduleName = schedule?.name ?: "",
      blockedApp = inFront,
      isBlocked = { it in blocks.apps },
      canOpen = { packageManager.getLaunchIntentForPackage(it) != null },
    )
    if (leaveBrowserPage) {
      // Press Back in the browser first, so the tab leaves the blocked page
      // (or closes, if it was opened just for it). Otherwise going back into
      // the browser lands on the same page and gets blocked all over again.
      performGlobalAction(GLOBAL_ACTION_BACK)
      handler.postDelayed({ respond(response) }, BACK_SETTLE_MS)
    } else {
      respond(response)
    }
  }

  private fun respond(response: BlockResponse) {
    when (response) {
      is BlockResponse.BlockScreen -> startActivity(
        Intent(this, BlockedActivity::class.java)
          .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP)
          .putExtra(BlockedActivity.EXTRA_HOST, response.label)
          .putExtra(BlockedActivity.EXTRA_MESSAGE, response.message),
      )

      is BlockResponse.OpenApp -> {
        val launch = packageManager.getLaunchIntentForPackage(response.packageName)
        if (launch == null) {
          // Uninstalled since the decision: block rather than let it through.
          respond(BlockResponse.BlockScreen(response.label))
          return
        }
        Log.i(TAG, "sending to ${response.packageName}")
        // Home first, so Back from the target app doesn't land on the
        // blocked one; then open the target once home has settled (opening
        // it straight away lets the home screen cover it).
        performGlobalAction(GLOBAL_ACTION_HOME)
        handler.postDelayed({
          startActivity(launch.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
          Toast.makeText(
            this,
            "${response.label} is blocked by \"${response.scheduleName}\"",
            Toast.LENGTH_LONG,
          ).show()
        }, HOME_SETTLE_MS)
      }
    }
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
    private const val HOME_SETTLE_MS = 400L
  }
}
