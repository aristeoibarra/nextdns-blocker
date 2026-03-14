package com.ndb.blocker

import android.graphics.drawable.GradientDrawable
import android.os.Bundle
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.LinearLayout
import android.widget.TextView
import androidx.fragment.app.Fragment

class BlockedFragment : Fragment() {

    private val engine: BlockerEngine
        get() = (requireActivity() as MainActivity).engine

    override fun onCreateView(inflater: LayoutInflater, container: ViewGroup?, savedInstanceState: Bundle?): View {
        return inflater.inflate(R.layout.fragment_blocked, container, false)
    }

    override fun onViewCreated(view: View, savedInstanceState: Bundle?) {
        super.onViewCreated(view, savedInstanceState)
        loadData()
    }

    fun loadData() {
        engine.getSyncState { state ->
            activity?.runOnUiThread { render(state) }
        }
    }

    private fun render(state: SyncState?) {
        val view = view ?: return

        val listContainer = view.findViewById<LinearLayout>(R.id.blockedListContainer)
        val tvSummary = view.findViewById<TextView>(R.id.tvBlockedSummary)
        val tvEmpty = view.findViewById<TextView>(R.id.tvEmptyBlocked)
        val summaryCard = view.findViewById<LinearLayout>(R.id.summaryCard)
        val summaryBreakdown = view.findViewById<LinearLayout>(R.id.summaryBreakdown)

        listContainer.removeAllViews()
        summaryBreakdown.removeAllViews()

        if (state == null || (state.blocked.isEmpty() && state.categories.isEmpty())) {
            tvSummary.text = ""
            tvEmpty.visibility = View.VISIBLE
            summaryCard.visibility = View.GONE
            return
        }
        tvEmpty.visibility = View.GONE

        // Group blocked apps by reason category
        val grouped = state.blocked.groupBy { entry ->
            val reason = entry.reason
            when {
                reason.startsWith("category:") -> reason
                reason.startsWith("denylist:") -> "denylist"
                else -> "other"
            }
        }.toSortedMap()

        // Summary card
        tvSummary.text = "${state.totalBlocked} apps blocked across ${grouped.size} groups"
        summaryCard.visibility = View.VISIBLE

        for ((group, entries) in grouped) {
            val label = formatGroupHeader(group)
            val color = if (group.startsWith("category:")) {
                Categories.colorForReason(group)
            } else {
                0xFF555555.toInt()
            }

            val row = LinearLayout(requireContext()).apply {
                orientation = LinearLayout.HORIZONTAL
                gravity = android.view.Gravity.CENTER_VERTICAL
                setPadding(0, 4, 0, 4)
            }

            val dot = View(requireContext()).apply {
                layoutParams = LinearLayout.LayoutParams(8, 8).apply { marginEnd = 10 }
                val drawable = GradientDrawable().apply {
                    shape = GradientDrawable.OVAL
                    setColor(color)
                }
                background = drawable
            }
            row.addView(dot)

            val tv = TextView(requireContext()).apply {
                text = "$label — ${entries.size}"
                textSize = 12f
                setTextColor(0xFFAAAAAA.toInt())
            }
            row.addView(tv)

            summaryBreakdown.addView(row)
        }

        // Collapsible sections per group
        for ((group, entries) in grouped) {
            val section = CollapsibleSection(requireContext())
            section.setTitle(formatGroupHeader(group))
            section.setCount(entries.size)

            val color = if (group.startsWith("category:")) {
                Categories.colorForReason(group)
            } else {
                0xFF555555.toInt()
            }
            section.setBarColor(color)

            val body = section.getContentContainer()

            for (entry in entries.sortedBy { it.name }) {
                val item = LayoutInflater.from(requireContext())
                    .inflate(R.layout.item_blocked_app, body, false)

                item.findViewById<TextView>(R.id.tvAppName).text = entry.name
                item.findViewById<TextView>(R.id.tvPackageName).text = entry.packageName

                val reasonText = entry.reason.substringAfter(":")
                item.findViewById<TextView>(R.id.tvReason).text = reasonText

                val colorBar = item.findViewById<View>(R.id.colorBar)
                val barDrawable = GradientDrawable().apply {
                    shape = GradientDrawable.RECTANGLE
                    cornerRadius = 2f
                    setColor(color)
                }
                colorBar.background = barDrawable

                body.addView(item)
            }

            listContainer.addView(section)
        }
    }

    private fun formatGroupHeader(group: String): String {
        return when {
            group.startsWith("category:") -> {
                val catId = group.removePrefix("category:")
                Categories.get(catId).displayName
            }
            group == "denylist" -> "Denylist"
            else -> group.replaceFirstChar { it.uppercase() }
        }
    }
}
