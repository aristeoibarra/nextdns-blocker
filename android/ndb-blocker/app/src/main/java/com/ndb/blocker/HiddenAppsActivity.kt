package com.ndb.blocker

import android.os.Bundle
import android.view.View
import android.widget.TextView
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import androidx.recyclerview.widget.LinearLayoutManager
import androidx.recyclerview.widget.RecyclerView

class HiddenAppsActivity : AppCompatActivity() {

    private lateinit var prefs: LauncherPrefs
    private lateinit var adapter: HiddenAppsAdapter

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_hidden_apps)

        prefs = LauncherPrefs(this)

        adapter = HiddenAppsAdapter { app ->
            prefs.unhidePackage(app.packageName)
            Toast.makeText(this, "${app.label} unhidden", Toast.LENGTH_SHORT).show()
            loadHidden()
        }

        val rv = findViewById<RecyclerView>(R.id.rvHidden)
        rv.layoutManager = LinearLayoutManager(this)
        rv.adapter = adapter

        loadHidden()
    }

    override fun onResume() {
        super.onResume()
        loadHidden()
    }

    private fun loadHidden() {
        val hidden = prefs.getHiddenPackages()
        val allApps = queryLaunchableApps(this)
        val hiddenApps = allApps.filter { it.packageName in hidden }

        adapter.submit(hiddenApps)

        val tvEmpty = findViewById<TextView>(R.id.tvEmpty)
        val rv = findViewById<RecyclerView>(R.id.rvHidden)
        tvEmpty.visibility = if (hiddenApps.isEmpty()) View.VISIBLE else View.GONE
        rv.visibility = if (hiddenApps.isEmpty()) View.GONE else View.VISIBLE
    }
}
