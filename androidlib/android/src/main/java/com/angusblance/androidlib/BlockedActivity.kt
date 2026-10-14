package com.angusblance.androidlib

import android.app.Activity
import android.content.Intent
import android.graphics.Color
import android.graphics.Typeface
import android.graphics.drawable.GradientDrawable
import android.os.Bundle
import android.view.Gravity
import android.widget.Button
import android.widget.LinearLayout
import android.widget.TextView

// Full-screen cover shown over the browser. Leaving it always goes to the
// home screen, never back into the blocked tab.
class BlockedActivity : Activity() {
  override fun onCreate(savedInstanceState: Bundle?) {
    super.onCreate(savedInstanceState)
    setContentView(buildView())
  }

  override fun onNewIntent(intent: Intent) {
    super.onNewIntent(intent)
    setIntent(intent)
    setContentView(buildView())
  }

  @Deprecated("Back always leaves to the home screen")
  override fun onBackPressed() {
    goHome()
  }

  // Same palette as android-mobile/src/theme.ts (Textual's dark theme).
  private fun buildView() = LinearLayout(this).apply {
    orientation = LinearLayout.VERTICAL
    gravity = Gravity.CENTER
    setBackgroundColor(BACKGROUND)
    setPadding(64, 64, 64, 64)

    val host = intent.getStringExtra(EXTRA_HOST) ?: "this site"
    addView(mono("BLOCKED", 14f, ACCENT).apply { setTypeface(typeface, Typeface.BOLD) })
    addView(mono(host, 22f, FOREGROUND).apply { setPadding(0, 16, 0, 16) })
    addView(
      mono("unblock it from the blocker app with your password.", 13f, MUTED).apply {
        setPadding(0, 0, 0, 56)
      },
    )
    addView(
      Button(context).apply {
        text = "go to home screen"
        typeface = Typeface.MONOSPACE
        isAllCaps = false
        setTextColor(BACKGROUND)
        background = GradientDrawable().apply { setColor(ACCENT) }
        setOnClickListener { goHome() }
      },
    )
  }

  private fun mono(value: String, sizeSp: Float, color: Int) = TextView(this).apply {
    text = value
    textSize = sizeSp
    typeface = Typeface.MONOSPACE
    setTextColor(color)
    gravity = Gravity.CENTER
  }

  private fun goHome() {
    startActivity(
      Intent(Intent.ACTION_MAIN)
        .addCategory(Intent.CATEGORY_HOME)
        .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK),
    )
    finish()
  }

  companion object {
    const val EXTRA_HOST = "host"
    private val BACKGROUND = Color.parseColor("#121212")
    private val FOREGROUND = Color.parseColor("#e0e0e0")
    private val MUTED = Color.parseColor("#8b8b8b")
    private val ACCENT = Color.parseColor("#ffa62b")
  }
}
