package com.ndb.blocker

import android.util.Log
import com.google.firebase.database.FirebaseDatabase
import com.google.firebase.messaging.FirebaseMessagingService
import com.google.firebase.messaging.RemoteMessage

class NdbFcmService : FirebaseMessagingService() {

    companion object {
        private const val TAG = "NdbFcmService"
    }

    override fun onMessageReceived(message: RemoteMessage) {
        if (message.data["action"] == "sync") {
            Log.i(TAG, "FCM sync push received")
            BlockerEngine(applicationContext).sync()
        }
    }

    override fun onNewToken(token: String) {
        Log.i(TAG, "FCM token refreshed")
        val deviceId = NdbConfig.DEVICE_ID
        FirebaseDatabase.getInstance()
            .getReference("devices/$deviceId/fcm_token")
            .setValue(token)
            .addOnFailureListener { e ->
                Log.e(TAG, "Failed to push FCM token, will retry on next sync", e)
            }
    }
}
