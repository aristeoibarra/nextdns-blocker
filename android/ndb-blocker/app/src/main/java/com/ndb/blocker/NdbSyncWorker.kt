package com.ndb.blocker

import android.content.Context
import android.util.Log
import androidx.work.Worker
import androidx.work.WorkerParameters
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit

class NdbSyncWorker(context: Context, params: WorkerParameters) : Worker(context, params) {

    companion object {
        private const val TAG = "NdbSyncWorker"
        private const val SYNC_TIMEOUT_SECONDS = 60L
    }

    override fun doWork(): Result {
        val latch = CountDownLatch(1)
        var syncSuccess = false

        BlockerEngine(applicationContext).sync { success ->
            syncSuccess = success
            latch.countDown()
        }

        val completed = latch.await(SYNC_TIMEOUT_SECONDS, TimeUnit.SECONDS)

        return if (completed && syncSuccess) {
            Log.i(TAG, "Sync completed successfully")
            Result.success()
        } else {
            Log.w(TAG, "Sync failed or timed out (completed=$completed, success=$syncSuccess)")
            Result.retry()
        }
    }
}
