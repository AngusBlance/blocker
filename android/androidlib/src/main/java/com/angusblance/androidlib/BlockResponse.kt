package com.angusblance.androidlib

// What the accessibility service does when something blocked comes up,
// decided from the schedule's action without touching Android, so it can be
// unit tested.
sealed interface BlockResponse {
  // The full-screen block page, with the schedule's message if it has one.
  data class BlockScreen(val label: String, val message: String? = null) : BlockResponse

  // Send the user to another app instead.
  data class OpenApp(val packageName: String) : BlockResponse

  companion object {
    // `blockedApp` is the app being blocked, if it's an app rather than a
    // site: redirecting to it would just open it again, so that blocks too.
    fun decide(
      action: Schedule.Action,
      label: String,
      blockedApp: String? = null,
      canOpen: (String) -> Boolean,
    ): BlockResponse = when (action) {
      Schedule.Action.Block -> BlockScreen(label)

      is Schedule.Action.Message -> BlockScreen(label, action.text.trim().ifEmpty { null })

      // If the target app is gone, still block rather than let it through.
      is Schedule.Action.Redirect ->
        if (action.packageName != blockedApp && canOpen(action.packageName)) {
          OpenApp(action.packageName)
        } else {
          BlockScreen(label)
        }
    }
  }
}
