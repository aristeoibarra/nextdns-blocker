package com.ndb.blocker

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.util.Log

class NdbBootReceiver : BroadcastReceiver() {

    companion object {
        private const val TAG = "NdbBootReceiver"
    }

    override fun onReceive(context: Context, intent: Intent) {
        if (intent.action == Intent.ACTION_BOOT_COMPLETED) {
            // Load cached blocked list immediately (before Firebase responds)
            val cached = NdbAccessibilityService.getBlockedPackages(context)
            if (cached.isNotEmpty()) {
                NdbAccessibilityService.updateBlockedPackages(context, cached)
                Log.i(TAG, "Loaded ${cached.size} cached blocked packages on boot")
            }

            // Then sync from Firebase (will update list if successful, preserve cache if not)
            BlockerEngine(context).sync()
        }
    }
}
