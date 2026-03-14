package com.ndb.blocker

import android.app.admin.DevicePolicyManager
import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.provider.Settings
import android.graphics.drawable.GradientDrawable
import android.os.Bundle
import android.view.GestureDetector
import android.view.LayoutInflater
import android.view.MotionEvent
import android.view.View
import android.widget.Button
import android.widget.HorizontalScrollView
import android.widget.LinearLayout
import android.widget.TextView
import androidx.appcompat.app.AppCompatActivity
import com.google.android.material.bottomsheet.BottomSheetDialog
import com.google.firebase.messaging.FirebaseMessaging
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

class MainActivity : AppCompatActivity() {

    lateinit var engine: BlockerEngine
        private set

    private lateinit var dpm: DevicePolicyManager
    private lateinit var adminComponent: ComponentName

    private var cachedSyncState: SyncState? = null
    private lateinit var gestureDetector: GestureDetector

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        engine = BlockerEngine(this)
        dpm = getSystemService(Context.DEVICE_POLICY_SERVICE) as DevicePolicyManager
        adminComponent = ComponentName(this, NdbDeviceAdmin::class.java)

        // Tap apps count → show blocked list
        findViewById<LinearLayout>(R.id.statsApps).setOnClickListener {
            showBlockedList()
        }

        // Tap service row → open accessibility settings if inactive
        findViewById<LinearLayout>(R.id.rowService).setOnClickListener {
            if (!NdbAccessibilityService.isRunning) {
                startActivity(Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS))
            }
        }

        // Swipe right → back to home
        gestureDetector = GestureDetector(this, object : GestureDetector.SimpleOnGestureListener() {
            override fun onFling(e1: MotionEvent?, e2: MotionEvent, vX: Float, vY: Float): Boolean {
                if (e1 == null) return false
                val dx = e2.x - e1.x
                val dy = e2.y - e1.y
                if (dx > 80 && kotlin.math.abs(dx) > kotlin.math.abs(dy)) {
                    goBack()
                    return true
                }
                return false
            }
        })

        // Sync button
        findViewById<Button>(R.id.btnSync).setOnClickListener {
            val btn = it as Button
            btn.isEnabled = false
            btn.text = "Syncing..."
            engine.sync()
            btn.postDelayed({
                refresh()
                btn.isEnabled = true
                btn.text = getString(R.string.btn_sync)
            }, 2500)
        }
    }

    override fun dispatchTouchEvent(ev: MotionEvent): Boolean {
        gestureDetector.onTouchEvent(ev)
        return super.dispatchTouchEvent(ev)
    }

    @Deprecated("Deprecated in Java")
    override fun onBackPressed() {
        goBack()
    }

    private fun goBack() {
        finish()
        overridePendingTransition(R.anim.slide_in_left, R.anim.slide_out_right)
    }

    override fun onResume() {
        super.onResume()
        refresh()
    }

    private fun refresh() {
        refreshProtection()
        refreshConfig()
        refreshDashboard()
        refreshLastSync()
    }

    private fun refreshProtection() {
        val dot = findViewById<View>(R.id.protectionDot)
        val tv = findViewById<TextView>(R.id.tvProtectionStatus)
        val running = NdbAccessibilityService.isRunning

        tv.text = if (running) "Active" else "Inactive"
        (dot.background as? GradientDrawable)?.setColor(
            if (running) 0xFF7A9E7E.toInt() else 0xFF555555.toInt()
        )
    }

    private fun refreshConfig() {
        // Service
        val serviceDot = findViewById<View>(R.id.serviceDot)
        val tvService = findViewById<TextView>(R.id.tvServiceStatus)
        val serviceRunning = NdbAccessibilityService.isRunning
        tvService.text = if (serviceRunning) "active" else "inactive"
        (serviceDot.background as? GradientDrawable)?.setColor(
            if (serviceRunning) 0xFF7A9E7E.toInt() else 0xFF555555.toInt()
        )

        // Admin
        val adminDot = findViewById<View>(R.id.adminDot)
        val tvAdmin = findViewById<TextView>(R.id.tvAdminStatus)
        val isAdmin = dpm.isAdminActive(adminComponent)
        tvAdmin.text = if (isAdmin) "active" else "inactive"
        (adminDot.background as? GradientDrawable)?.setColor(
            if (isAdmin) 0xFF7A9E7E.toInt() else 0xFF333333.toInt()
        )

        // Firebase
        val fcmDot = findViewById<View>(R.id.fcmDot)
        val tvFcm = findViewById<TextView>(R.id.tvFcmStatus)
        FirebaseMessaging.getInstance().token.addOnSuccessListener { token ->
            runOnUiThread {
                if (token.isNullOrEmpty()) {
                    tvFcm.text = "disconnected"
                    (fcmDot.background as? GradientDrawable)?.setColor(0xFF555555.toInt())
                } else {
                    tvFcm.text = "connected"
                    (fcmDot.background as? GradientDrawable)?.setColor(0xFF7A9E7E.toInt())
                }
            }
        }.addOnFailureListener {
            runOnUiThread {
                tvFcm.text = "error"
                (fcmDot.background as? GradientDrawable)?.setColor(0xFF555555.toInt())
            }
        }
    }

    private fun refreshDashboard() {
        engine.getDashboardState { dashboard ->
            runOnUiThread {
                val tvApps = findViewById<TextView>(R.id.tvAppsBlocked)
                val tvDns = findViewById<TextView>(R.id.tvDnsBlocked)
                val tvPending = findViewById<TextView>(R.id.tvPendingCount)
                val chipContainer = findViewById<LinearLayout>(R.id.chipContainer)
                val chipScroll = findViewById<HorizontalScrollView>(R.id.chipScrollView)

                if (dashboard == null) {
                    engine.getBlockedCount { count ->
                        runOnUiThread { tvApps.text = count.toString() }
                    }
                    return@runOnUiThread
                }

                tvApps.text = dashboard.appsBlocked.toString()
                tvDns.text = dashboard.dnsBlocked.toString()

                val pending = dashboard.pendingActions.size
                tvPending.text = pending.toString()
                tvPending.setTextColor(if (pending == 0) 0xFF555555.toInt() else 0xFFFFFFFF.toInt())

                // Category chips
                chipContainer.removeAllViews()
                if (dashboard.categories.isNotEmpty()) {
                    chipScroll.visibility = View.VISIBLE
                    for (catId in dashboard.categories) {
                        val info = Categories.get(catId)
                        val chip = LayoutInflater.from(this)
                            .inflate(R.layout.item_category_chip, chipContainer, false)
                        chip.findViewById<TextView>(R.id.chipLabel).text = info.displayName
                        val dot = chip.findViewById<View>(R.id.chipDot)
                        (dot.background as? GradientDrawable)?.setColor(info.color)
                        chipContainer.addView(chip)
                    }
                } else {
                    chipScroll.visibility = View.GONE
                }
            }
        }

        // Cache sync state for bottom sheet
        engine.getSyncState { state ->
            cachedSyncState = state
        }
    }

    private fun refreshLastSync() {
        val tvLastSync = findViewById<TextView>(R.id.tvLastSync)
        engine.getLastSync { timestamp ->
            runOnUiThread {
                tvLastSync.text = if (timestamp != null) {
                    SimpleDateFormat("HH:mm", Locale.getDefault()).format(Date(timestamp * 1000))
                } else {
                    "never"
                }
            }
        }
    }

    private fun showBlockedList() {
        val state = cachedSyncState ?: return
        if (state.blocked.isEmpty()) return

        val dialog = BottomSheetDialog(this, R.style.Theme_NdbBlocker_BottomSheet)
        val view = layoutInflater.inflate(R.layout.bottom_sheet_blocked_list, null)

        view.findViewById<TextView>(R.id.tvSheetTitle).text = "${state.blocked.size} apps blocked"

        val container = view.findViewById<LinearLayout>(R.id.listContainer)
        for (entry in state.blocked.sortedBy { it.name }) {
            val row = TextView(this).apply {
                text = entry.name
                textSize = 18f
                setTextColor(0xFFFFFFFF.toInt())
                typeface = android.graphics.Typeface.create("sans-serif-light", android.graphics.Typeface.NORMAL)
                setPadding(0, 12, 0, 12)
            }
            container.addView(row)
        }

        dialog.setContentView(view)
        dialog.show()
    }
}
