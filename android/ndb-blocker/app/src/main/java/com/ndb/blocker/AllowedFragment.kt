package com.ndb.blocker

import android.graphics.Typeface
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
        // Load both sync state (apps) and dns state (domains)
        engine.getSyncState { syncState ->
            engine.getDnsState { dnsState ->
                activity?.runOnUiThread { render(syncState, dnsState) }
            }
        }
    }

    private fun render(syncState: SyncState?, dnsState: DnsState?) {
        val view = view ?: return

        val listContainer = view.findViewById<LinearLayout>(R.id.allowedListContainer)
        val tvSummary = view.findViewById<TextView>(R.id.tvAllowedSummary)
        val tvEmpty = view.findViewById<TextView>(R.id.tvEmptyAllowed)

        listContainer.removeAllViews()

        val allowedApps = syncState?.allowed ?: emptyList()
        val allowedDomains = dnsState?.allowedDomains ?: emptyList()

        if (allowedApps.isEmpty() && allowedDomains.isEmpty()) {
            tvSummary.text = ""
            tvEmpty.visibility = View.VISIBLE
            return
        }
        tvEmpty.visibility = View.GONE

        val parts = mutableListOf<String>()
        if (allowedApps.isNotEmpty()) parts.add("${allowedApps.size} apps")
        if (allowedDomains.isNotEmpty()) parts.add("${allowedDomains.size} domains")
        tvSummary.text = "${parts.joinToString(" + ")} allowed"

        // Apps Allowed section
        if (allowedApps.isNotEmpty()) {
            val section = CollapsibleSection(requireContext())
            section.setTitle("APPS ALLOWED")
            section.setCount(allowedApps.size)
            section.setBarColor(0xFF4CAF50.toInt())

            val body = section.getContentContainer()
            for (entry in allowedApps.sortedBy { it.name }) {
                val item = LayoutInflater.from(requireContext())
                    .inflate(R.layout.item_allowed_app, body, false)

                item.findViewById<TextView>(R.id.tvAppName).text = entry.name
                item.findViewById<TextView>(R.id.tvPackageName).text = entry.packageName

                val reasonText = entry.reason.substringAfter(":")
                item.findViewById<TextView>(R.id.tvReason).text = reasonText

                body.addView(item)
            }

            listContainer.addView(section)
        }

        // Domains Allowed section
        if (allowedDomains.isNotEmpty()) {
            val section = CollapsibleSection(requireContext())
            section.setTitle("DOMAINS ALLOWED")
            section.setCount(allowedDomains.size)
            section.setBarColor(0xFF4CAF50.toInt())

            val body = section.getContentContainer()
            for (d in allowedDomains.sortedBy { it.domain }) {
                val row = LinearLayout(requireContext()).apply {
                    orientation = LinearLayout.HORIZONTAL
                    gravity = android.view.Gravity.CENTER_VERTICAL
                    setPadding(4, 8, 4, 8)
                }

                val bar = View(requireContext()).apply {
                    layoutParams = LinearLayout.LayoutParams(3, 28).apply { marginEnd = 12 }
                    setBackgroundColor(0xFF4CAF50.toInt())
                }
                row.addView(bar)

                val textCol = LinearLayout(requireContext()).apply {
                    orientation = LinearLayout.VERTICAL
                    layoutParams = LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f)
                }

                val domainTv = TextView(requireContext()).apply {
                    text = d.domain
                    textSize = 13f
                    setTextColor(0xFFE0E0E0.toInt())
                    typeface = Typeface.MONOSPACE
                }
                textCol.addView(domainTv)

                if (!d.description.isNullOrEmpty()) {
                    val descTv = TextView(requireContext()).apply {
                        text = d.description
                        textSize = 11f
                        setTextColor(0xFF666666.toInt())
                    }
                    textCol.addView(descTv)
                }

                row.addView(textCol)
                body.addView(row)
            }

            listContainer.addView(section)
        }
    }
}
