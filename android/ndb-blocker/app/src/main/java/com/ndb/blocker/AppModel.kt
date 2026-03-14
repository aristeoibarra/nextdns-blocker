package com.ndb.blocker

import android.content.Context
import android.content.Intent

data class AppModel(
    val packageName: String,
    val label: String
)

fun queryLaunchableApps(context: Context): List<AppModel> {
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
