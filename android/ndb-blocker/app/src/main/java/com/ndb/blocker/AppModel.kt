package com.ndb.blocker

import android.content.Context
import android.content.Intent

data class AppModel(
    val packageName: String,
    val label: String
)

object AppCache {
    private var cached: List<AppModel>? = null
    private var cacheTime: Long = 0
    private const val TTL_MS = 30_000L // 30 seconds

    fun get(context: Context): List<AppModel> {
        val now = System.currentTimeMillis()
        cached?.let {
            if (now - cacheTime < TTL_MS) return it
        }
        val apps = queryFromSystem(context)
        cached = apps
        cacheTime = now
        return apps
    }

    fun invalidate() {
        cached = null
    }

    private fun queryFromSystem(context: Context): List<AppModel> {
        val pm = context.packageManager
        val intent = Intent(Intent.ACTION_MAIN).apply {
            addCategory(Intent.CATEGORY_LAUNCHER)
        }
        val seen = mutableSetOf<String>()
        return pm.queryIntentActivities(intent, 0)
            .mapNotNull { ri ->
                val pkg = ri.activityInfo.packageName
                if (pkg == context.packageName) return@mapNotNull null
                if (!seen.add(pkg)) return@mapNotNull null
                val label = ri.loadLabel(pm).toString()
                AppModel(pkg, label)
            }
            .sortedBy { it.label.lowercase() }
    }
}

fun queryLaunchableApps(context: Context): List<AppModel> = AppCache.get(context)
