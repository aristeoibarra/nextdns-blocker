package com.ndb.blocker

data class SyncState(
    val categories: List<String>,
    val blocked: List<AppEntry>,
    val allowed: List<AppEntry>,
    val totalBlocked: Int,
    val totalAllowed: Int,
    val syncedAt: Long
)

data class AppEntry(
    val packageName: String,
    val name: String,
    val reason: String
)
