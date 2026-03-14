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

        val chipContainer = view.findViewById<LinearLayout>(R.id.chipContainer)
        val listContainer = view.findViewById<LinearLayout>(R.id.blockedListContainer)
        val tvSummary = view.findViewById<TextView>(R.id.tvBlockedSummary)
        val tvEmpty = view.findViewById<TextView>(R.id.tvEmptyBlocked)

        chipContainer.removeAllViews()
        listContainer.removeAllViews()

        if (state == null || (state.blocked.isEmpty() && state.categories.isEmpty())) {
            tvSummary.text = ""
            tvEmpty.visibility = View.VISIBLE
            return
        }
        tvEmpty.visibility = View.GONE

        tvSummary.text = "${state.totalBlocked} apps blocked"

        // Render category chips
        for (catId in state.categories) {
            val info = Categories.get(catId)
            val chip = LayoutInflater.from(requireContext())
                .inflate(R.layout.item_category_chip, chipContainer, false)

            chip.findViewById<TextView>(R.id.chipLabel).text = info.displayName
            val dot = chip.findViewById<View>(R.id.chipDot)
            val dotDrawable = dot.background as? GradientDrawable
            dotDrawable?.setColor(info.color)

            chipContainer.addView(chip)
        }

        // Group blocked apps by reason category
        val grouped = state.blocked.groupBy { entry ->
            val reason = entry.reason
            when {
                reason.startsWith("category:") -> reason
                reason.startsWith("denylist:") -> "denylist"
                else -> "other"
            }
        }.toSortedMap()

        for ((group, entries) in grouped) {
            // Section header
            val header = TextView(requireContext()).apply {
                text = formatGroupHeader(group)
                textSize = 12f
                setTextColor(0xFF888888.toInt())
                letterSpacing = 0.08f
                setPadding(4, 24, 0, 8)
            }
            listContainer.addView(header)

            // Divider
            val divider = View(requireContext()).apply {
                layoutParams = LinearLayout.LayoutParams(
                    LinearLayout.LayoutParams.MATCH_PARENT, 1
                ).apply { bottomMargin = 4 }
                setBackgroundColor(0xFF2A2A2A.toInt())
            }
            listContainer.addView(divider)

            // App entries
            for (entry in entries.sortedBy { it.name }) {
                val item = LayoutInflater.from(requireContext())
                    .inflate(R.layout.item_blocked_app, listContainer, false)

                item.findViewById<TextView>(R.id.tvAppName).text = entry.name
                item.findViewById<TextView>(R.id.tvPackageName).text = entry.packageName

                val reasonText = entry.reason.substringAfter(":")
                item.findViewById<TextView>(R.id.tvReason).text = reasonText

                val colorBar = item.findViewById<View>(R.id.colorBar)
                val barDrawable = GradientDrawable().apply {
                    shape = GradientDrawable.RECTANGLE
                    cornerRadius = 2f
                    setColor(Categories.colorForReason(entry.reason))
                }
                colorBar.background = barDrawable

                listContainer.addView(item)
            }
        }
    }

    private fun formatGroupHeader(group: String): String {
        return when {
            group.startsWith("category:") -> {
                val catId = group.removePrefix("category:")
                Categories.get(catId).displayName.uppercase()
            }
            group == "denylist" -> "DENYLIST"
            else -> group.uppercase()
        }
    }
}
