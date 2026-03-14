package com.ndb.blocker

import android.graphics.Color

data class CategoryInfo(
    val id: String,
    val displayName: String,
    val color: Int
)

object Categories {
    private val registry = mapOf(
        "social-networks" to CategoryInfo("social-networks", "Social Networks", Color.parseColor("#E040FB")),
        "video-streaming" to CategoryInfo("video-streaming", "Video Streaming", Color.parseColor("#FF5252")),
        "gaming" to CategoryInfo("gaming", "Gaming", Color.parseColor("#69F0AE")),
        "dating" to CategoryInfo("dating", "Dating", Color.parseColor("#FF4081")),
        "gambling" to CategoryInfo("gambling", "Gambling", Color.parseColor("#FFD740")),
    )

    fun get(id: String): CategoryInfo {
        return registry[id] ?: CategoryInfo(id, id.replace('-', ' ')
            .replaceFirstChar { it.uppercase() }, Color.parseColor("#888888"))
    }

    fun colorForReason(reason: String): Int {
        if (!reason.startsWith("category:")) return Color.parseColor("#BB86FC")
        val catId = reason.removePrefix("category:")
        return get(catId).color
    }
}
