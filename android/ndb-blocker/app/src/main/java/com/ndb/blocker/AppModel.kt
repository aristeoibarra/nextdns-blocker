package com.ndb.blocker

import android.content.Context
import android.content.Intent
import android.graphics.drawable.Drawable

data class AppModel(
    val packageName: String,
    val label: String,
    val icon: Drawable?
)

fun queryLaunchableApps(context: Context): List<AppModel> {
    val pm = context.packageManager
    val intent = Intent(Intent.ACTION_MAIN).apply {
        addCategory(Intent.CATEGORY_LAUNCHER)
    }
    return pm.queryIntentActivities(intent, 0)
        .mapNotNull { ri ->
            val pkg = ri.activityInfo.packageName
            if (pkg == context.packageName) return@mapNotNull null
            val label = ri.loadLabel(pm).toString()
            val icon = try { ri.loadIcon(pm) } catch (_: Exception) { null }
            AppModel(pkg, label, icon)
        }
        .sortedBy { it.label.lowercase() }
}
