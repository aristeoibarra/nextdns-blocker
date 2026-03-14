package com.ndb.blocker

import android.graphics.Color

data class CategoryInfo(
    val id: String,
    val displayName: String,
    val color: Int
)

object Categories {
    private val registry = mapOf(
        "social-networks" to CategoryInfo("social-networks", "Social", Color.parseColor("#888888")),
        "video-streaming" to CategoryInfo("video-streaming", "Video", Color.parseColor("#777777")),
        "gaming" to CategoryInfo("gaming", "Gaming", Color.parseColor("#999999")),
        "dating" to CategoryInfo("dating", "Dating", Color.parseColor("#777777")),
        "gambling" to CategoryInfo("gambling", "Gambling", Color.parseColor("#888888")),
        "piracy" to CategoryInfo("piracy", "Piracy", Color.parseColor("#666666")),
        "porn" to CategoryInfo("porn", "Porn", Color.parseColor("#666666")),
    )

    fun get(id: String): CategoryInfo {
        return registry[id] ?: CategoryInfo(id, id.replace('-', ' ')
            .replaceFirstChar { it.uppercase() }, Color.parseColor("#555555"))
    }

    fun colorForReason(reason: String): Int {
        if (!reason.startsWith("category:")) return Color.parseColor("#555555")
        val catId = reason.removePrefix("category:")
        return get(catId).color
    }
}
