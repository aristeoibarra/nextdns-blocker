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
import com.google.firebase.database.FirebaseDatabase
import com.google.firebase.messaging.FirebaseMessaging

class SettingsFragment : Fragment() {

    private lateinit var dpm: DevicePolicyManager
    private lateinit var adminComponent: ComponentName

    override fun onCreateView(inflater: LayoutInflater, container: ViewGroup?, savedInstanceState: Bundle?): View {
        return inflater.inflate(R.layout.fragment_settings, container, false)
    }

    override fun onViewCreated(view: View, savedInstanceState: Bundle?) {
        super.onViewCreated(view, savedInstanceState)
        dpm = requireContext().getSystemService(Context.DEVICE_POLICY_SERVICE) as DevicePolicyManager
        adminComponent = ComponentName(requireContext(), NdbDeviceAdmin::class.java)

        view.findViewById<Button>(R.id.btnEnable).setOnClickListener {
            startActivity(Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS))
        }

        view.findViewById<Button>(R.id.btnDeviceAdmin).setOnClickListener {
            if (dpm.isAdminActive(adminComponent)) {
                dpm.removeActiveAdmin(adminComponent)
                refreshSettings()
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
        refreshSettings()
    }

    fun refreshSettings() {
        val view = view ?: return

        // Accessibility Service status
        val tvServiceStatus = view.findViewById<TextView>(R.id.tvServiceStatus)
        val tvServiceHint = view.findViewById<TextView>(R.id.tvServiceHint)
        val btnEnable = view.findViewById<Button>(R.id.btnEnable)
        val statusDot = view.findViewById<View>(R.id.statusDot)

        val running = NdbAccessibilityService.isRunning

        tvServiceStatus.text = if (running) getString(R.string.status_active) else getString(R.string.status_inactive)
        tvServiceHint.text = if (running) getString(R.string.hint_active) else getString(R.string.hint_inactive)
        btnEnable.text = if (running) getString(R.string.btn_settings) else getString(R.string.btn_enable)

        val dotDrawable = statusDot.background as? GradientDrawable
        dotDrawable?.setColor(if (running) 0xFF4CAF50.toInt() else 0xFFF44336.toInt())

        // Device Admin status
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

        // Firebase info
        val tvFirebaseProject = view.findViewById<TextView>(R.id.tvFirebaseProject)
        val tvFcmStatus = view.findViewById<TextView>(R.id.tvFcmStatus)
        val fcmDot = view.findViewById<View>(R.id.fcmDot)

        val firebaseApp = try {
            com.google.firebase.FirebaseApp.getInstance()
        } catch (_: Exception) { null }

        tvFirebaseProject.text = firebaseApp?.options?.projectId ?: getString(R.string.status_not_configured)

        FirebaseMessaging.getInstance().token.addOnSuccessListener { token ->
            activity?.runOnUiThread {
                val fcmDotDrawable = fcmDot.background as? GradientDrawable
                if (token.isNullOrEmpty()) {
                    tvFcmStatus.text = getString(R.string.status_not_registered)
                    fcmDotDrawable?.setColor(0xFFF44336.toInt())
                } else {
                    tvFcmStatus.text = getString(R.string.status_registered)
                    fcmDotDrawable?.setColor(0xFF4CAF50.toInt())
                }
            }
        }.addOnFailureListener {
            activity?.runOnUiThread {
                tvFcmStatus.text = getString(R.string.status_error)
                val fcmDotDrawable = fcmDot.background as? GradientDrawable
                fcmDotDrawable?.setColor(0xFFF44336.toInt())
            }
        }
    }
}
