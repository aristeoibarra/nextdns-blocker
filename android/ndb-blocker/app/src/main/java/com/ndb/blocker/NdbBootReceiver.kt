package com.ndb.blocker

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent

class NdbBootReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        if (intent.action == Intent.ACTION_BOOT_COMPLETED) {
            BlockerEngine(context).sync()
        }
    }
}
