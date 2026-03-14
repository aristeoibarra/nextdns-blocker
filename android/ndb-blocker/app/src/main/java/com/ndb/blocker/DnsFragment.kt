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

        tvSummary.text = "${state.totalBlockedDomains} blocked \u00B7 ${state.totalAllowedDomains} allowed"

        for (cat in state.customCategories.sortedByDescending { it.count }) {
            addCategorySection(container, cat)
        }

        if (state.uncategorized.isNotEmpty()) {
            val section = CollapsibleSection(requireContext())
            section.setTitle("Uncategorized")
            section.setCount(state.uncategorized.size)
            section.setBarColor(0xFF555555.toInt())

            val body = section.getContentContainer()
            for (domain in state.uncategorized.sortedBy { it.domain }) {
                addDomainRow(body, domain.domain, domain.description, 0xFF333333.toInt())
            }
            container.addView(section)
        }

        if (state.allowedDomains.isNotEmpty()) {
            val section = CollapsibleSection(requireContext())
            section.setTitle("Allowed")
            section.setCount(state.allowedDomains.size)
            section.setBarColor(0xFF7A9E7E.toInt())

            val body = section.getContentContainer()
            for (domain in state.allowedDomains.sortedBy { it.domain }) {
                addDomainRow(body, domain.domain, domain.description, 0xFF7A9E7E.toInt())
            }
            container.addView(section)
        }
    }

    private fun addCategorySection(container: LinearLayout, cat: DnsCategory) {
        val section = CollapsibleSection(requireContext())
        section.setTitle(cat.name.replace('-', ' ').replaceFirstChar { it.uppercase() })
        section.setCount(cat.count)
        section.setBarColor(0xFF555555.toInt())

        val body = section.getContentContainer()

        if (!cat.description.isNullOrEmpty()) {
            val desc = TextView(requireContext()).apply {
                text = cat.description
                textSize = 12f
                setTextColor(0xFF555555.toInt())
                setPadding(4, 8, 0, 12)
            }
            body.addView(desc)
        }

        if (!cat.schedule.isNullOrEmpty()) {
            val sched = TextView(requireContext()).apply {
                text = "\u23F0 Scheduled"
                textSize = 11f
                setTextColor(0xFF555555.toInt())
                setPadding(4, 0, 0, 8)
            }
            body.addView(sched)
        }

        for (d in cat.domains.sortedBy { it.domain }) {
            addDomainRow(body, d.domain, d.description, 0xFF333333.toInt())
        }

        container.addView(section)
    }

    private fun addDomainRow(container: LinearLayout, domain: String, description: String?, accentColor: Int) {
        val row = LinearLayout(requireContext()).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = android.view.Gravity.CENTER_VERTICAL
            setPadding(4, 8, 4, 8)
        }

        val bar = View(requireContext()).apply {
            layoutParams = LinearLayout.LayoutParams(2, 24).apply { marginEnd = 12 }
            setBackgroundColor(accentColor)
        }
        row.addView(bar)

        val textCol = LinearLayout(requireContext()).apply {
            orientation = LinearLayout.VERTICAL
            layoutParams = LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f)
        }

        val domainTv = TextView(requireContext()).apply {
            text = domain
            textSize = 13f
            setTextColor(0xFFFFFFFF.toInt())
            typeface = Typeface.MONOSPACE
        }
        textCol.addView(domainTv)

        if (!description.isNullOrEmpty()) {
            val descTv = TextView(requireContext()).apply {
                text = description
                textSize = 11f
                setTextColor(0xFF444444.toInt())
            }
            textCol.addView(descTv)
        }

        row.addView(textCol)
        container.addView(row)
    }
}
