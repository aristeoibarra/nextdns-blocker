package com.ndb.blocker

import android.graphics.drawable.GradientDrawable
import android.os.Bundle
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.LinearLayout
import android.widget.TextView
import androidx.fragment.app.Fragment

class AllowedFragment : Fragment() {

    private val engine: BlockerEngine
        get() = (requireActivity() as MainActivity).engine

    override fun onCreateView(inflater: LayoutInflater, container: ViewGroup?, savedInstanceState: Bundle?): View {
        return inflater.inflate(R.layout.fragment_allowed, container, false)
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

        val listContainer = view.findViewById<LinearLayout>(R.id.allowedListContainer)
        val tvSummary = view.findViewById<TextView>(R.id.tvAllowedSummary)
        val tvEmpty = view.findViewById<TextView>(R.id.tvEmptyAllowed)

        listContainer.removeAllViews()

        val allowed = state?.allowed ?: emptyList()

        if (allowed.isEmpty()) {
            tvSummary.text = ""
            tvEmpty.visibility = View.VISIBLE
            return
        }
        tvEmpty.visibility = View.GONE

        tvSummary.text = "${allowed.size} apps allowed"

        for (entry in allowed.sortedBy { it.name }) {
            val item = LayoutInflater.from(requireContext())
                .inflate(R.layout.item_allowed_app, listContainer, false)

            item.findViewById<TextView>(R.id.tvAppName).text = entry.name
            item.findViewById<TextView>(R.id.tvPackageName).text = entry.packageName

            val reasonText = entry.reason.substringAfter(":")
            item.findViewById<TextView>(R.id.tvReason).text = reasonText

            listContainer.addView(item)
        }
    }
}
