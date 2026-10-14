package com.angusblance.androidlib

import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.net.Uri
import android.os.Bundle
import android.provider.Settings
import expo.modules.kotlin.exception.Exceptions
import expo.modules.kotlin.modules.Module
import expo.modules.kotlin.modules.ModuleDefinition

// The JS API android-mobile calls. Everything here goes through BlockStore,
// the same store the accessibility service reads.
class AndroidlibModule : Module() {
  private val context: Context
    get() = appContext.reactContext ?: throw Exceptions.ReactContextLost()

  private val store get() = BlockStore(context)

  private val serviceComponent
    get() = ComponentName(context, BlockerAccessibilityService::class.java)

  private fun tryStart(intent: Intent): Boolean = try {
    context.startActivity(intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
    true
  } catch (e: Exception) {
    false
  }

  override fun definition() = ModuleDefinition {
    Name("Androidlib")

    Function("getBlockedDomains") {
      store.blockedDomains.sorted()
    }

    Function("getBlockedApps") {
      store.blockedApps.sorted()
    }

    Function("block") { domains: List<String>, apps: List<String> ->
      store.block(domains, apps)
    }

    Function("unblock") { password: String, domains: List<String>, apps: List<String> ->
      store.unblock(password, domains, apps)
    }

    Function("getUnlockPassword") {
      store.unlockPassword
    }

    Function("isServiceEnabled") {
      val enabled = Settings.Secure.getString(
        context.contentResolver,
        Settings.Secure.ENABLED_ACCESSIBILITY_SERVICES,
      ) ?: ""
      enabled.split(':').any { ComponentName.unflattenFromString(it) == serviceComponent }
    }

    // Straight to Blocker's own on/off page where Android allows it,
    // otherwise the accessibility list with Blocker highlighted (Pixel-style
    // settings honour the fragment args key; others ignore it).
    Function("openAccessibilitySettings") {
      val component = serviceComponent.flattenToString()
      val details = Intent("android.settings.ACCESSIBILITY_DETAILS_SETTINGS")
        .putExtra(Intent.EXTRA_COMPONENT_NAME, component)
      val list = Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS)
        .putExtra(":settings:fragment_args_key", component)
        .putExtra(
          ":settings:show_fragment_args",
          Bundle().apply {
            putString(":settings:fragment_args_key", component)
          },
        )
      tryStart(details) || tryStart(list)
    }

    Function("openAppInfo") {
      tryStart(
        Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS)
          .setData(Uri.parse("package:${context.packageName}")),
      )
    }
  }
}
