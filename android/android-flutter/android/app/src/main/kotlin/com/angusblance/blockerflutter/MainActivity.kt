package com.angusblance.blockerflutter

import android.content.ComponentName
import android.content.Intent
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.provider.Settings
import com.angusblance.androidlib.BlockStore
import com.angusblance.androidlib.BlockerAccessibilityService
import com.angusblance.androidlib.Schedule
import com.angusblance.androidlib.ScheduleRules
import com.angusblance.androidlib.ScheduleStore
import io.flutter.embedding.android.FlutterActivity
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.plugin.common.MethodChannel

// The Dart UI's way into androidlib, over a Flutter method channel.
class MainActivity : FlutterActivity() {
  private val store by lazy { BlockStore(this) }

  @Volatile private var appsCache: List<Map<String, String>>? = null

  private fun loadApps(): List<Map<String, String>> {
    val launcher = Intent(Intent.ACTION_MAIN).addCategory(Intent.CATEGORY_LAUNCHER)
    return packageManager.queryIntentActivities(launcher, 0)
      .map { it.activityInfo.packageName to it.loadLabel(packageManager).toString() }
      .filter { it.first != packageName }
      .distinctBy { it.first }
      .sortedBy { it.second.lowercase() }
      .map { (pkg, label) -> mapOf("package" to pkg, "label" to label) }
  }
  private val schedules by lazy { ScheduleStore(this) }

  private val serviceComponent
    get() = ComponentName(this, BlockerAccessibilityService::class.java)

  override fun configureFlutterEngine(flutterEngine: FlutterEngine) {
    super.configureFlutterEngine(flutterEngine)
    MethodChannel(flutterEngine.dartExecutor.binaryMessenger, CHANNEL).setMethodCallHandler {
        call,
        result,
      ->
      when (call.method) {
        "getBlockedDomains" -> result.success(store.blockedDomains.sorted())

        "getBlockedApps" -> result.success(store.blockedApps.sorted())

        "block" -> {
          store.block(call.list("domains"), call.list("apps"))
          result.success(null)
        }

        "unblock" -> result.success(
          store.unblock(
            call.argument<String>("password") ?: "",
            call.list("domains"),
            call.list("apps"),
          ),
        )

        "getUnlockPassword" -> result.success(store.unlockPassword)

        // Schedules travel as the JSON Schedule.kt and schedule.dart share.
        "getSchedules" -> result.success(
          Schedule.listToJson(schedules.schedules),
        )

        "saveSchedules" -> try {
          schedules.replaceAll(
            call.argument<String>("json") ?: "",
            call.argument<String>("password"),
          )
          result.success(null)
        } catch (e: ScheduleRules.LockedException) {
          result.error("locked", e.message, null)
        } catch (e: IllegalArgumentException) {
          result.error("bad_schedules", e.message, null)
        } catch (e: Exception) {
          // e.g. storage refusing the write; the app shows it.
          result.error("error", e.message, null)
        }

        "scheduleStatus" -> result.success(schedules.statusJson())

        "nextSchedule" -> result.success(schedules.nextJson())

        // "paused", "wrong_password" or "not_running".
        "pauseSchedule" -> try {
          val outcome = schedules.pause(
            call.argument<String>("id") ?: "",
            call.argument<String>("password") ?: "",
          )
          result.success(outcome.name.lowercase())
        } catch (e: Exception) {
          result.error("error", e.message, null)
        }

        // Apps a schedule can send you to instead: everything with a launcher
        // icon except Blocker itself, sorted by name. Loading every app's name
        // is slow, so it's done off the main thread and kept for next time.
        "installedApps" -> {
          appsCache?.let {
            result.success(it)
            return@setMethodCallHandler
          }
          Thread {
            val apps = runCatching { loadApps() }
            runOnUiThread {
              apps.onSuccess {
                appsCache = it
                result.success(it)
              }.onFailure { result.error("error", it.message, null) }
            }
          }.start()
        }

        "isServiceEnabled" -> result.success(isServiceEnabled())

        "sdkInt" -> result.success(Build.VERSION.SDK_INT)

        "openAccessibilitySettings" -> {
          openAccessibilitySettings()
          result.success(null)
        }

        "openAppInfo" -> {
          tryStart(
            Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS)
              .setData(Uri.parse("package:$packageName")),
          )
          result.success(null)
        }

        else -> result.notImplemented()
      }
    }
  }

  private fun io.flutter.plugin.common.MethodCall.list(name: String): List<String> =
    argument<List<String>>(name) ?: emptyList()

  private fun isServiceEnabled(): Boolean {
    val enabled =
      Settings.Secure.getString(contentResolver, Settings.Secure.ENABLED_ACCESSIBILITY_SERVICES)
        ?: ""
    return enabled.split(':').any { ComponentName.unflattenFromString(it) == serviceComponent }
  }

  // Straight to Blocker's own page where Android allows it, otherwise the
  // accessibility list with Blocker highlighted.
  private fun openAccessibilitySettings() {
    val component = serviceComponent.flattenToString()
    val details = Intent("android.settings.ACCESSIBILITY_DETAILS_SETTINGS")
      .putExtra(Intent.EXTRA_COMPONENT_NAME, component)
    val list = Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS)
      .putExtra(":settings:fragment_args_key", component)
      .putExtra(
        ":settings:show_fragment_args",
        Bundle().apply { putString(":settings:fragment_args_key", component) },
      )
    tryStart(details) || tryStart(list)
  }

  private fun tryStart(intent: Intent): Boolean = try {
    startActivity(intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
    true
  } catch (e: Exception) {
    false
  }

  companion object {
    const val CHANNEL = "com.angusblance.blocker/backend"
  }
}
