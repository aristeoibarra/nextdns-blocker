package com.ndb.blocker

data class DashboardState(
    val appsBlocked: Int,
    val dnsBlocked: Int,
    val categories: List<String>,
    val pendingActions: List<PendingActionEntry>,
    val syncedAt: Long
)

data class PendingActionEntry(
    val domain: String,
    val action: String,
    val executeAt: Long,
    val description: String?
)
