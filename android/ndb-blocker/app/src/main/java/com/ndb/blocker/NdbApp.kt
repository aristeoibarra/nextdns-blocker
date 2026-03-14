package com.ndb.blocker

import android.app.Application
import androidx.work.BackoffPolicy
import androidx.work.ExistingPeriodicWorkPolicy
import androidx.work.PeriodicWorkRequestBuilder
import androidx.work.WorkManager
import com.google.firebase.FirebaseApp
import java.util.concurrent.TimeUnit

class NdbApp : Application() {
    override fun onCreate() {
        super.onCreate()
        FirebaseApp.initializeApp(this)

        val syncRequest = PeriodicWorkRequestBuilder<NdbSyncWorker>(15, TimeUnit.MINUTES)
            .setBackoffCriteria(BackoffPolicy.EXPONENTIAL, 30, TimeUnit.SECONDS)
            .build()

        WorkManager.getInstance(this).enqueueUniquePeriodicWork(
            "ndb-sync",
            ExistingPeriodicWorkPolicy.KEEP,
            syncRequest
        )
    }
}
