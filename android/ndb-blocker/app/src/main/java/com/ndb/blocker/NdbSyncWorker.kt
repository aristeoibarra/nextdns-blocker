package com.ndb.blocker

import android.content.Context
import androidx.work.Worker
import androidx.work.WorkerParameters

class NdbSyncWorker(context: Context, params: WorkerParameters) : Worker(context, params) {
    override fun doWork(): Result {
        BlockerEngine(applicationContext).sync()
        return Result.success()
    }
}
