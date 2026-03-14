package com.ndb.blocker

import android.app.admin.DevicePolicyManager
import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.graphics.drawable.GradientDrawable
import android.os.Bundle
import android.provider.Settings
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.Button
import android.widget.TextView
import androidx.fragment.app.Fragment
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

class StatusFragment : Fragment() {

    private lateinit var dpm: DevicePolicyManager
    private lateinit var adminComponent: ComponentName

    private val engine: BlockerEngine
        get() = (requireActivity() as MainActivity).engine

    override fun onCreateView(inflater: LayoutInflater, container: ViewGroup?, savedInstanceState: Bundle?): View {
        return inflater.inflate(R.layout.fragment_status, container, false)
    }

    override fun onViewCreated(view: View, savedInstanceState: Bundle?) {
        super.onViewCreated(view, savedInstanceState)
        dpm = requireContext().getSystemService(Context.DEVICE_POLICY_SERVICE) as DevicePolicyManager
        adminComponent = ComponentName(requireContext(), NdbDeviceAdmin::class.java)

        view.findViewById<Button>(R.id.btnEnable).setOnClickListener {
            startActivity(Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS))
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
                // Notify other tabs
                (requireActivity() as? MainActivity)?.onSyncComplete()
            }, 2500)
        }

        view.findViewById<Button>(R.id.btnDeviceAdmin).setOnClickListener {
            if (dpm.isAdminActive(adminComponent)) {
                dpm.removeActiveAdmin(adminComponent)
                refreshStatus()
            } else {
                val intent = Intent(DevicePolicyManager.ACTION_ADD_DEVICE_ADMIN).apply {
                    putExtra(DevicePolicyManager.EXTRA_DEVICE_ADMIN, adminComponent)
                    putExtra(DevicePolicyManager.EXTRA_ADD_EXPLANATION,
                        "Prevents ndb blocker from being uninstalled.")
                }
                startActivity(intent)
            }
        }
    }

    override fun onResume() {
        super.onResume()
        refreshStatus()
    }

    fun refreshStatus() {
        val view = view ?: return

        val tvServiceStatus = view.findViewById<TextView>(R.id.tvServiceStatus)
        val tvServiceHint = view.findViewById<TextView>(R.id.tvServiceHint)
        val tvLastSync = view.findViewById<TextView>(R.id.tvLastSync)
        val tvBlockedCount = view.findViewById<TextView>(R.id.tvBlockedCount)
        val btnEnable = view.findViewById<Button>(R.id.btnEnable)
        val statusDot = view.findViewById<View>(R.id.statusDot)

        val running = NdbAccessibilityService.isRunning

        tvServiceStatus.text = if (running) getString(R.string.status_active) else getString(R.string.status_inactive)
        tvServiceHint.text = if (running) getString(R.string.hint_active) else getString(R.string.hint_inactive)
        btnEnable.text = if (running) getString(R.string.btn_settings) else getString(R.string.btn_enable)

        val dotDrawable = statusDot.background as? GradientDrawable
        dotDrawable?.setColor(if (running) 0xFF4CAF50.toInt() else 0xFFF44336.toInt())

        // Device Admin
        val tvAdminStatus = view.findViewById<TextView>(R.id.tvAdminStatus)
        val tvAdminHint = view.findViewById<TextView>(R.id.tvAdminHint)
        val btnDeviceAdmin = view.findViewById<Button>(R.id.btnDeviceAdmin)
        val adminDot = view.findViewById<View>(R.id.adminDot)

        val isAdmin = dpm.isAdminActive(adminComponent)

        tvAdminStatus.text = if (isAdmin) getString(R.string.admin_active) else getString(R.string.admin_inactive)
        tvAdminHint.text = if (isAdmin) getString(R.string.admin_hint_active) else getString(R.string.admin_hint_inactive)
        btnDeviceAdmin.text = if (isAdmin) getString(R.string.btn_disable_admin) else getString(R.string.btn_enable_admin)

        val adminDotDrawable = adminDot.background as? GradientDrawable
        adminDotDrawable?.setColor(if (isAdmin) 0xFF4CAF50.toInt() else 0xFF666666.toInt())

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

        engine.getBlockedCount { count ->
            activity?.runOnUiThread {
                tvBlockedCount.text = count.toString()
            }
        }
    }
}
