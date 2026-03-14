package com.ndb.blocker

import android.graphics.Typeface
import android.os.Bundle
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.LinearLayout
import android.widget.TextView
import androidx.fragment.app.Fragment

class DnsFragment : Fragment() {

    private val engine: BlockerEngine
        get() = (requireActivity() as MainActivity).engine

    override fun onCreateView(inflater: LayoutInflater, container: ViewGroup?, savedInstanceState: Bundle?): View {
        return inflater.inflate(R.layout.fragment_dns, container, false)
    }

    override fun onViewCreated(view: View, savedInstanceState: Bundle?) {
        super.onViewCreated(view, savedInstanceState)
        loadData()
    }

    fun loadData() {
        engine.getDnsState { state ->
            activity?.runOnUiThread { render(state) }
        }
    }

    private fun render(state: DnsState?) {
        val view = view ?: return

        val container = view.findViewById<LinearLayout>(R.id.dnsListContainer)
        val tvSummary = view.findViewById<TextView>(R.id.tvDnsSummary)
        val tvEmpty = view.findViewById<TextView>(R.id.tvEmptyDns)

        container.removeAllViews()

        if (state == null || (state.customCategories.isEmpty() && state.uncategorized.isEmpty())) {
            tvSummary.text = ""
            tvEmpty.visibility = View.VISIBLE
            return
        }
        tvEmpty.visibility = View.GONE

        tvSummary.text = "${state.totalBlockedDomains} domains blocked · ${state.totalAllowedDomains} allowed"

        // Render custom categories
        for (cat in state.customCategories.sortedByDescending { it.count }) {
            addCategoryCard(container, cat)
        }

        // Uncategorized denylist
        if (state.uncategorized.isNotEmpty()) {
            addSectionHeader(container, "UNCATEGORIZED", state.uncategorized.size)
            for (domain in state.uncategorized.sortedBy { it.domain }) {
                addDomainRow(container, domain.domain, domain.description, 0xFFF44336.toInt())
            }
        }

        // Allowed domains
        if (state.allowedDomains.isNotEmpty()) {
            addSectionHeader(container, "ALLOWED", state.allowedDomains.size)
            for (domain in state.allowedDomains.sortedBy { it.domain }) {
                addDomainRow(container, domain.domain, domain.description, 0xFF4CAF50.toInt())
            }
        }
    }

    private fun addCategoryCard(container: LinearLayout, cat: DnsCategory) {
        // Section header with count
        addSectionHeader(container, cat.name.uppercase().replace('-', ' '), cat.count)

        // Description
        if (!cat.description.isNullOrEmpty()) {
            val desc = TextView(requireContext()).apply {
                text = cat.description
                textSize = 12f
                setTextColor(0xFF888888.toInt())
                setPadding(4, 0, 0, 12)
            }
            container.addView(desc)
        }

        // Domain list
        for (domain in cat.domains.sorted()) {
            addDomainRow(container, domain, null, 0xFFF44336.toInt())
        }

        // Spacer
        val spacer = View(requireContext()).apply {
            layoutParams = LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT, 16
            )
        }
        container.addView(spacer)
    }

    private fun addSectionHeader(container: LinearLayout, title: String, count: Int) {
        val header = LinearLayout(requireContext()).apply {
            orientation = LinearLayout.HORIZONTAL
            setPadding(4, 24, 4, 8)
            gravity = android.view.Gravity.CENTER_VERTICAL
        }

        val titleTv = TextView(requireContext()).apply {
            text = title
            textSize = 12f
            setTextColor(0xFF888888.toInt())
            letterSpacing = 0.08f
            typeface = Typeface.DEFAULT_BOLD
            layoutParams = LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f)
        }
        header.addView(titleTv)

        val countTv = TextView(requireContext()).apply {
            text = count.toString()
            textSize = 12f
            setTextColor(0xFF555555.toInt())
        }
        header.addView(countTv)

        container.addView(header)

        // Divider
        val divider = View(requireContext()).apply {
            layoutParams = LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT, 1
            ).apply { bottomMargin = 4 }
            setBackgroundColor(0xFF2A2A2A.toInt())
        }
        container.addView(divider)
    }

    private fun addDomainRow(container: LinearLayout, domain: String, description: String?, accentColor: Int) {
        val row = LinearLayout(requireContext()).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = android.view.Gravity.CENTER_VERTICAL
            setPadding(4, 8, 4, 8)
        }

        // Color bar
        val bar = View(requireContext()).apply {
            layoutParams = LinearLayout.LayoutParams(3, 28).apply { marginEnd = 12 }
            setBackgroundColor(accentColor)
        }
        row.addView(bar)

        // Domain text
        val domainTv = TextView(requireContext()).apply {
            text = domain
            textSize = 13f
            setTextColor(0xFFE0E0E0.toInt())
            typeface = Typeface.MONOSPACE
            layoutParams = LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f)
        }
        row.addView(domainTv)

        container.addView(row)
    }
}
