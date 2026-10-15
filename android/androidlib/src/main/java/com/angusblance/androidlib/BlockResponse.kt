package com.angusblance.androidlib

// What the accessibility service does when something blocked comes up,
// decided from the schedule's action without touching Android, so it can be
// unit tested.
sealed interface BlockResponse {
  // The full-screen block page, with the schedule's message if it has one.
  data class BlockScreen(val label: String, val message: String? = null) : BlockResponse

  // Send the user to another app instead. `label` is what was blocked and
  // `scheduleName` the schedule doing it, for a short explanation.
  data class OpenApp(val packageName: String, val label: String, val scheduleName: String) :
    BlockResponse

  companion object {
    // Longer messages are cut short so the block screen's button stays on it.
    const val MAX_MESSAGE = 200

    // `blockedApp` is the app in front: the blocked app itself, or the
    // browser a blocked site is open in. Redirecting there would change
    // nothing. Redirecting to anything that's blocked itself could bounce
    // between two redirect schedules forever, so both of those block instead.
    fun decide(
      action: Schedule.Action,
      label: String,
      scheduleName: String = "",
      blockedApp: String? = null,
      isBlocked: (String) -> Boolean = { false },
      canOpen: (String) -> Boolean,
    ): BlockResponse = when (action) {
      Schedule.Action.Block -> BlockScreen(label)

      is Schedule.Action.Message -> BlockScreen(label, shorten(action.text.trim()).ifEmpty { null })

      // If the target app is gone, still block rather than let it through.
      is Schedule.Action.Redirect -> {
        val target = action.packageName
        if (target != blockedApp && !isBlocked(target) && canOpen(target)) {
          OpenApp(target, label, scheduleName)
        } else {
          BlockScreen(label)
        }
      }
    }

    private fun shorten(text: String) = if (text.length <=
      MAX_MESSAGE
    ) {
      text
    } else {
      text.take(MAX_MESSAGE - 1).trimEnd() + "…"
    }
  }
}
