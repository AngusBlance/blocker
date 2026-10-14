package com.angusblance.androidlib

import android.content.ComponentName
import android.content.Context
import android.content.Intent
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

  override fun definition() = ModuleDefinition {
    Name("Androidlib")

    Function("getBlockedDomains") {
      store.blockedDomains.sorted()
    }

    Function("block") { domains: List<String> ->
      store.block(domains)
    }

    Function("unblock") { password: String, domains: List<String> ->
      store.unblock(password, domains)
    }

    Function("getUnlockPassword") {
      store.unlockPassword
    }

    Function("isServiceEnabled") {
      val expected = ComponentName(context, BlockerAccessibilityService::class.java)
      val enabled = Settings.Secure.getString(
        context.contentResolver,
        Settings.Secure.ENABLED_ACCESSIBILITY_SERVICES,
      ) ?: ""
      enabled.split(':').any { ComponentName.unflattenFromString(it) == expected }
    }

    Function("openAccessibilitySettings") {
      context.startActivity(
        Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
      )
    }
  }
}
