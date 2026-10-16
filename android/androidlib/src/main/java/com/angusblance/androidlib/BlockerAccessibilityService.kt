package com.angusblance.androidlib

import android.accessibilityservice.AccessibilityService
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Handler
import android.os.Looper
import android.os.SystemClock
import android.telecom.TelecomManager
import android.util.Log
import android.view.accessibility.AccessibilityEvent
import android.view.inputmethod.InputMethodManager
import android.widget.Toast
import java.time.Instant
import java.time.ZoneId
import java.time.ZonedDateTime
import java.time.format.DateTimeFormatter

// Covers the screen with BlockedActivity when a blocked app comes to the
// front, or when a browser's address bar shows a blocked site. Android starts
// and keeps this running on its own once the user enables it, independent of
// the Flutter UI.
class BlockerAccessibilityService : AccessibilityService() {
  private lateinit var store: ScheduleStore
  private lateinit var manual: BlockStore
  private lateinit var focusStore: FocusStore
  private var alwaysAllowed: Set<String> = emptySet()
  private var alwaysAllowedAt = 0L
  private var lastBlocked: String? = null
  private var lastBlockedAt = 0L
  private val handler = Handler(Looper.getMainLooper())

  override fun onServiceConnected() {
    store = ScheduleStore(this)
    manual = BlockStore(this)
    focusStore = FocusStore(this)
    // If the adult filter is on, read its list off the main thread now, so
    // the first page doesn't wait for it. (Otherwise it's read when needed.)
    val adultOn = AdultSites.ID in manual.blockedDomains ||
      runCatching { AdultSites.ID in store.activeBlocks().domains }.getOrDefault(false)
    if (adultOn) Thread { AdultSites.get(this) }.start()
    Log.i(TAG, "connected")
  }

  override fun onAccessibilityEvent(event: AccessibilityEvent) {
    val packageName = event.packageName?.toString() ?: return
    // Focus first: it allows a few things and blocks the rest. What it lets
    // through still goes through the usual blocks below (they stack).
    val focus = runCatching { focusStore.active() }.getOrElse {
      Log.e(TAG, "focus unreadable", it)
      null
    }
    if (focus != null && checkFocus(packageName, focus)) return
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
    if (BrowserUrlBars.idsFor(packageName) == null) return
    val blocked = blocks.domains
    if (blocked.isEmpty()) return
    val address = currentAddress(packageName) ?: return
    val host = UrlMatcher.hostOf(address) ?: return
    val match = UrlMatcher.blockedBy(address, blocked) { AdultSites.get(this) } ?: return
    // A schedule covers Google Images or the adult filter by listing it, not
    // the host it's on.
    val listed = if (match == UrlMatcher.GOOGLE_IMAGES || match == AdultSites.ID) match else host
    val label = if (match == UrlMatcher.GOOGLE_IMAGES) "Google Images" else host
    show(
      host,
      label,
      blocks,
      blocks.scheduleFor(host = listed),
      packageName,
      leaveBrowserPage = true,
    )
  }

  // The site a known browser in front is showing, or null if there isn't
  // one (or the user is typing in the address bar).
  private fun currentHost(packageName: String): String? =
    currentAddress(packageName)?.let(UrlMatcher::hostOf)

  // What the browser's address bar shows, unless it's being typed in.
  private fun currentAddress(packageName: String): String? {
    val barIds = BrowserUrlBars.idsFor(packageName) ?: return null
    val root = rootInActiveWindow ?: return null
    val bar = barIds.firstNotNullOfOrNull { id ->
      root.findAccessibilityNodeInfosByViewId(id).firstOrNull()
    } ?: return null
    // While the user is typing, the bar holds a half-finished address.
    if (bar.isFocused) return null
    return bar.text?.toString()
  }

  // True if focus blocked what's in front.
  private fun checkFocus(packageName: String, focus: Focus): Boolean =
    when (FocusRules.appVerdict(packageName, focus, alwaysAllowed())) {
      FocusRules.AppVerdict.ALLOWED -> false

      FocusRules.AppVerdict.BLOCKED -> {
        // Only when it's actually in front, not e.g. a notification it posted.
        if (rootInActiveWindow?.packageName?.toString() != packageName) {
          false
        } else {
          showFocus(packageName, appLabel(packageName), focus)
          true
        }
      }

      FocusRules.AppVerdict.CHECK_URL -> {
        val host = currentHost(packageName)
        if (host == null || FocusRules.hostAllowed(host, focus)) {
          false
        } else {
          showFocus(host, host, focus, leaveBrowserPage = true)
          true
        }
      }
    }

  private fun showFocus(
    key: String,
    label: String,
    focus: Focus,
    leaveBrowserPage: Boolean = false,
  ) {
    val now = SystemClock.elapsedRealtime()
    if (key == lastBlocked && now - lastBlockedAt < DEBOUNCE_MS) return
    lastBlocked = key
    lastBlockedAt = now
    Log.i(TAG, "focus: blocking $key")
    val until = Instant.ofEpochMilli(focus.endsAt).atZone(ZoneId.systemDefault())
      .format(DateTimeFormatter.ofPattern("HH:mm"))
    val allowed = (focus.sites + focus.apps.map { appLabel(it) }).distinct()
    val response = BlockResponse.BlockScreen(
      label,
      "Focus is on until $until. Only ${allowed.joinToString(", ")} can be open.",
    )
    if (leaveBrowserPage) {
      performGlobalAction(GLOBAL_ACTION_BACK)
      handler.postDelayed({ respond(response) }, BACK_SETTLE_MS)
    } else {
      respond(response)
    }
  }

  // This app, the home screen(s), the keyboard(s) and the phone app: looked
  // up on the phone (they differ by maker and by what the user installed),
  // at most once a minute.
  private fun alwaysAllowed(): Set<String> {
    val now = SystemClock.elapsedRealtime()
    if (alwaysAllowed.isNotEmpty() &&
      now - alwaysAllowedAt < ALLOWED_REFRESH_MS
    ) {
      return alwaysAllowed
    }
    val found = mutableSetOf(packageName)
    runCatching {
      val home = Intent(Intent.ACTION_MAIN).addCategory(Intent.CATEGORY_HOME)
      packageManager.queryIntentActivities(home, 0)
        .map { it.activityInfo.packageName }
        // Settings has a fallback home screen too; it isn't a launcher.
        .filterTo(found) { it !in NOT_LAUNCHERS }
    }
    runCatching {
      getSystemService(InputMethodManager::class.java)?.enabledInputMethodList
        ?.mapTo(found) { it.packageName }
    }
    runCatching {
      getSystemService(TelecomManager::class.java)?.defaultDialerPackage?.let { found += it }
    }
    alwaysAllowed = found
    alwaysAllowedAt = now
    return found
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
    private const val ALLOWED_REFRESH_MS = 60_000L
    private val NOT_LAUNCHERS = setOf("com.android.settings")
  }
}
