package com.ndb.blocker

import android.graphics.drawable.GradientDrawable
import android.os.Bundle
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.Button
import android.widget.LinearLayout
import android.widget.TextView
import androidx.fragment.app.Fragment
import com.google.android.material.bottomnavigation.BottomNavigationView
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

class StatusFragment : Fragment() {

    private val engine: BlockerEngine
        get() = (requireActivity() as MainActivity).engine

    override fun onCreateView(inflater: LayoutInflater, container: ViewGroup?, savedInstanceState: Bundle?): View {
        return inflater.inflate(R.layout.fragment_status, container, false)
    }

    override fun onViewCreated(view: View, savedInstanceState: Bundle?) {
        super.onViewCreated(view, savedInstanceState)

        // Tap protection banner → navigate to Settings tab
        view.findViewById<LinearLayout>(R.id.protectionBanner).setOnClickListener {
            requireActivity().findViewById<BottomNavigationView>(R.id.bottomNavigation)
                .selectedItemId = R.id.nav_settings
        }

        view.findViewById<Button>(R.id.btnSync).setOnClickListener {
            val btn = it as Button
            btn.isEnabled = false
            btn.text = "Syncing..."
            engine.sync()
            btn.postDelayed({
                refreshStatus()
                btn.isEnabled = true
                btn.text = getString(R.string.btn_sync)
                (requireActivity() as? MainActivity)?.onSyncComplete()
            }, 2500)
        }
    }

    override fun onResume() {
        super.onResume()
        refreshStatus()
    }

    fun refreshStatus() {
        val view = view ?: return

        val tvLastSync = view.findViewById<TextView>(R.id.tvLastSync)

        // Protection status banner
        val tvProtectionStatus = view.findViewById<TextView>(R.id.tvProtectionStatus)
        val protectionDot = view.findViewById<View>(R.id.protectionDot)
        val running = NdbAccessibilityService.isRunning
        tvProtectionStatus.text = if (running) getString(R.string.status_active) else getString(R.string.status_inactive)
        val protectionDotDrawable = protectionDot.background as? GradientDrawable
        protectionDotDrawable?.setColor(if (running) 0xFF4CAF50.toInt() else 0xFFF44336.toInt())

        // Dashboard state from Firebase
        engine.getDashboardState { dashboard ->
            activity?.runOnUiThread { renderDashboard(dashboard) }
        }

        // Last sync time
        engine.getLastSync { timestamp ->
            activity?.runOnUiThread {
                tvLastSync.text = if (timestamp != null) {
                    val fmt = SimpleDateFormat("HH:mm:ss", Locale.getDefault())
                    fmt.format(Date(timestamp * 1000))
                } else {
                    getString(R.string.status_never)
                }
            }
        }
    }

    private fun renderDashboard(dashboard: DashboardState?) {
        val view = view ?: return

        val tvAppsBlocked = view.findViewById<TextView>(R.id.tvAppsBlocked)
        val tvDnsBlocked = view.findViewById<TextView>(R.id.tvDnsBlocked)
        val tvPendingCount = view.findViewById<TextView>(R.id.tvPendingCount)
        val chipContainer = view.findViewById<LinearLayout>(R.id.chipContainer)
        val chipScrollView = view.findViewById<View>(R.id.chipScrollView)
        val tvCategoriesLabel = view.findViewById<View>(R.id.tvCategoriesLabel)
        val pendingCard = view.findViewById<LinearLayout>(R.id.pendingCard)
        val pendingList = view.findViewById<LinearLayout>(R.id.pendingList)

        if (dashboard == null) {
            // Fallback: use blocked count from sync
            engine.getBlockedCount { count ->
                activity?.runOnUiThread {
                    tvAppsBlocked.text = count.toString()
                }
            }
            return
        }

        // Stats grid
        tvAppsBlocked.text = dashboard.appsBlocked.toString()
        tvDnsBlocked.text = dashboard.dnsBlocked.toString()

        val pending = dashboard.pendingActions.size
        tvPendingCount.text = pending.toString()
        tvPendingCount.setTextColor(if (pending == 0) 0xFF4CAF50.toInt() else 0xFFFFD740.toInt())

        // Category chips
        chipContainer.removeAllViews()
        if (dashboard.categories.isNotEmpty()) {
            tvCategoriesLabel.visibility = View.VISIBLE
            chipScrollView.visibility = View.VISIBLE

            for (catId in dashboard.categories) {
                val info = Categories.get(catId)
                val chip = LayoutInflater.from(requireContext())
                    .inflate(R.layout.item_category_chip, chipContainer, false)

                chip.findViewById<TextView>(R.id.chipLabel).text = info.displayName
                val dot = chip.findViewById<View>(R.id.chipDot)
                val chipDotDrawable = dot.background as? GradientDrawable
                chipDotDrawable?.setColor(info.color)

                chipContainer.addView(chip)
            }
        } else {
            tvCategoriesLabel.visibility = View.GONE
            chipScrollView.visibility = View.GONE
        }

        // Pending actions card
        pendingList.removeAllViews()
        if (dashboard.pendingActions.isNotEmpty()) {
            pendingCard.visibility = View.VISIBLE

            val now = System.currentTimeMillis() / 1000
            val items = dashboard.pendingActions.take(5)

            for (entry in items) {
                val row = LinearLayout(requireContext()).apply {
                    orientation = LinearLayout.HORIZONTAL
                    gravity = android.view.Gravity.CENTER_VERTICAL
                    setPadding(0, 6, 0, 6)
                }

                val domainTv = TextView(requireContext()).apply {
                    text = entry.domain
                    textSize = 13f
                    setTextColor(0xFFE0E0E0.toInt())
                    layoutParams = LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f)
                }
                row.addView(domainTv)

                val remaining = entry.executeAt - now
                val timeText = if (remaining > 0) {
                    val h = remaining / 3600
                    val m = (remaining % 3600) / 60
                    if (h > 0) "${entry.action}s in ${h}h ${m}m"
                    else "${entry.action}s in ${m}m"
                } else {
                    "${entry.action}s now"
                }

                val timeTv = TextView(requireContext()).apply {
                    text = timeText
                    textSize = 12f
                    setTextColor(0xFFFFD740.toInt())
                }
                row.addView(timeTv)

                pendingList.addView(row)
            }
        } else {
            pendingCard.visibility = View.GONE
        }
    }
}
