package com.ndb.blocker

import android.util.Log
import com.google.firebase.database.FirebaseDatabase
import com.google.firebase.messaging.FirebaseMessagingService
import com.google.firebase.messaging.RemoteMessage

class NdbFcmService : FirebaseMessagingService() {

    companion object {
        private const val TAG = "NdbFcmService"
        private const val DEVICE_ID = "android_pixel"
    }

    override fun onMessageReceived(message: RemoteMessage) {
        if (message.data["action"] == "sync") {
            Log.i(TAG, "FCM sync push received")
            BlockerEngine(applicationContext).sync()
        }
    }

    override fun onNewToken(token: String) {
        Log.i(TAG, "FCM token refreshed")
        FirebaseDatabase.getInstance()
            .getReference("devices/$DEVICE_ID/fcm_token")
            .setValue(token)
    }
}
