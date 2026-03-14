package com.ndb.blocker

import android.accessibilityservice.AccessibilityService
import android.accessibilityservice.AccessibilityServiceInfo
import android.content.Context
import android.util.Log
import android.view.accessibility.AccessibilityEvent
import android.widget.Toast

class NdbAccessibilityService : AccessibilityService() {

    companion object {
        private const val TAG = "NdbAccessibility"
        private const val PREFS_NAME = "ndb_blocked"
        private const val KEY_BLOCKED = "blocked_packages"

        @Volatile
        var isRunning = false
            private set

        private var blockedPackages: Set<String> = emptySet()

        fun updateBlockedPackages(context: Context, packages: Set<String>) {
            blockedPackages = packages
            context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
                .edit()
                .putStringSet(KEY_BLOCKED, packages)
                .apply()
        }

        fun getBlockedPackages(context: Context): Set<String> {
            return context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
                .getStringSet(KEY_BLOCKED, emptySet()) ?: emptySet()
        }
    }

    override fun onServiceConnected() {
        isRunning = true
        blockedPackages = getBlockedPackages(this)

        serviceInfo = AccessibilityServiceInfo().apply {
            eventTypes = AccessibilityEvent.TYPE_WINDOW_STATE_CHANGED
            feedbackType = AccessibilityServiceInfo.FEEDBACK_GENERIC
            notificationTimeout = 100
            flags = AccessibilityServiceInfo.FLAG_INCLUDE_NOT_IMPORTANT_VIEWS
        }

        Log.i(TAG, "Service connected, ${blockedPackages.size} packages blocked")
    }

    override fun onAccessibilityEvent(event: AccessibilityEvent?) {
        if (event?.eventType != AccessibilityEvent.TYPE_WINDOW_STATE_CHANGED) return

        val pkg = event.packageName?.toString() ?: return

        // Don't block system UI, settings, or ourselves
        if (pkg == packageName || pkg == "com.android.systemui" || pkg == "com.android.settings") return

        if (pkg in blockedPackages) {
            Log.i(TAG, "Blocked: $pkg")
            BlockedActivity.launch(this, pkg)
        }
    }

    override fun onInterrupt() {}

    override fun onDestroy() {
        isRunning = false
        super.onDestroy()
    }
}
