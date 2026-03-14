package com.ndb.blocker

import android.content.Intent
import android.os.Bundle
import android.provider.Settings
import android.widget.Button
import android.widget.TextView
import androidx.appcompat.app.AppCompatActivity
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

class MainActivity : AppCompatActivity() {

    private lateinit var engine: BlockerEngine

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)
        engine = BlockerEngine(this)

        findViewById<Button>(R.id.btnEnable).setOnClickListener {
            startActivity(Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS))
        }

        findViewById<Button>(R.id.btnSync).setOnClickListener {
            engine.sync()
            // Refresh after a short delay to let Firebase respond
            it.postDelayed({ refreshStatus() }, 2000)
        }
    }

    override fun onResume() {
        super.onResume()
        refreshStatus()
    }

    private fun refreshStatus() {
        val tvServiceStatus = findViewById<TextView>(R.id.tvServiceStatus)
        val tvLastSync = findViewById<TextView>(R.id.tvLastSync)
        val tvBlockedCount = findViewById<TextView>(R.id.tvBlockedCount)
        val btnEnable = findViewById<Button>(R.id.btnEnable)

        val running = NdbAccessibilityService.isRunning
        tvServiceStatus.text = if (running) getString(R.string.status_active) else getString(R.string.status_inactive)
        tvServiceStatus.setTextColor(if (running) 0xFF4CAF50.toInt() else 0xFFF44336.toInt())
        btnEnable.text = if (running) getString(R.string.btn_settings) else getString(R.string.btn_enable)

        engine.getLastSync { timestamp ->
            runOnUiThread {
                tvLastSync.text = if (timestamp != null) {
                    val fmt = SimpleDateFormat("yyyy-MM-dd HH:mm:ss", Locale.getDefault())
                    fmt.format(Date(timestamp * 1000))
                } else {
                    getString(R.string.status_never)
                }
            }
        }

        engine.getBlockedCount { count ->
            runOnUiThread {
                tvBlockedCount.text = count.toString()
            }
        }
    }
}
