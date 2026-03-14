package com.ndb.blocker

import android.content.ComponentName
import android.content.Intent
import android.content.SharedPreferences
import android.os.Bundle
import android.view.GestureDetector
import android.view.MotionEvent
import android.view.View
import android.widget.TextView
import android.widget.Toast
import androidx.appcompat.app.AlertDialog
import androidx.appcompat.app.AppCompatActivity
import androidx.core.view.WindowCompat
import androidx.core.view.WindowInsetsCompat
import androidx.core.view.WindowInsetsControllerCompat
import androidx.recyclerview.widget.LinearLayoutManager
import androidx.recyclerview.widget.RecyclerView
import kotlin.math.abs

class LauncherActivity : AppCompatActivity() {

    private lateinit var prefs: LauncherPrefs
    private lateinit var adapter: HomeAdapter
    private lateinit var rvFavorites: RecyclerView
    private lateinit var gestureDetector: GestureDetector

    private val blockedPrefsListener = SharedPreferences.OnSharedPreferenceChangeListener { _, key ->
        if (key == "blocked_packages") refreshFavorites()
    }

    private val launcherPrefsListener = SharedPreferences.OnSharedPreferenceChangeListener { _, key ->
        if (key == "favorites") refreshFavorites()
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_launcher)

        // Immersive: hide status bar
        WindowCompat.setDecorFitsSystemWindows(window, false)
        WindowCompat.getInsetsController(window, window.decorView).let {
            it.hide(WindowInsetsCompat.Type.statusBars())
            it.systemBarsBehavior = WindowInsetsControllerCompat.BEHAVIOR_SHOW_TRANSIENT_BARS_BY_SWIPE
        }

        prefs = LauncherPrefs(this)
        rvFavorites = findViewById(R.id.rvFavorites)
        adapter = HomeAdapter(
            onTap = { pkg -> launchApp(pkg) },
            onLongPress = { pkg, label -> confirmRemoveFavorite(pkg, label) }
        )

        rvFavorites.layoutManager = LinearLayoutManager(this)
        rvFavorites.adapter = adapter

        // Gesture detector for swipe left → drawer, long press → stock launcher
        gestureDetector = GestureDetector(this, object : GestureDetector.SimpleOnGestureListener() {
            override fun onFling(e1: MotionEvent?, e2: MotionEvent, vX: Float, vY: Float): Boolean {
                if (e1 == null) return false
                val dx = e2.x - e1.x
                val dy = e2.y - e1.y
                if (dx > 80 && abs(dx) > abs(dy)) {
                    openDrawer()
                    return true
                }
                if (dx < -80 && abs(dx) > abs(dy)) {
                    openSettings()
                    return true
                }
                return false
            }

            // Long press disabled — no action on home
        })

        // Touch handling done via dispatchTouchEvent override
    }

    override fun dispatchTouchEvent(ev: MotionEvent): Boolean {
        gestureDetector.onTouchEvent(ev)
        return super.dispatchTouchEvent(ev)
    }

    override fun onResume() {
        super.onResume()
        refreshFavorites()
        getSharedPreferences("ndb_blocked", MODE_PRIVATE)
            .registerOnSharedPreferenceChangeListener(blockedPrefsListener)
        prefs.registerListener(launcherPrefsListener)
    }

    override fun onPause() {
        super.onPause()
        getSharedPreferences("ndb_blocked", MODE_PRIVATE)
            .unregisterOnSharedPreferenceChangeListener(blockedPrefsListener)
        prefs.unregisterListener(launcherPrefsListener)
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        refreshFavorites()
    }

    @Deprecated("Deprecated in Java")
    override fun onBackPressed() {
        // Launcher absorbs back press — do nothing
    }

    private fun refreshFavorites() {
        val blocked = NdbAccessibilityService.getBlockedPackages(this)
        val favoritePackages = prefs.getFavorites().filter { it !in blocked }

        val allApps = queryLaunchableApps(this)
        val appMap = allApps.associateBy { it.packageName }

        val resolved = favoritePackages.mapNotNull { appMap[it] }
        adapter.submit(resolved)

        rvFavorites.visibility = if (resolved.isEmpty()) View.GONE else View.VISIBLE
    }

    private fun launchApp(pkg: String) {
        val intent = packageManager.getLaunchIntentForPackage(pkg) ?: return
        startActivity(intent)
    }

    private fun confirmRemoveFavorite(pkg: String, label: String) {
        AlertDialog.Builder(this, R.style.Theme_NdbBlocker_Dialog)
            .setMessage("Remove \"$label\"?")
            .setPositiveButton("Remove") { _, _ ->
                prefs.removeFavorite(pkg)
                refreshFavorites()
            }
            .setNegativeButton("Cancel", null)
            .show()
    }

    private fun openDrawer() {
        startActivity(Intent(this, DrawerActivity::class.java))
        overridePendingTransition(R.anim.slide_in_left, R.anim.slide_out_right)
    }

    private fun openSettings() {
        startActivity(Intent(this, MainActivity::class.java))
        overridePendingTransition(R.anim.slide_in_right, R.anim.slide_out_left)
    }

    private fun openStockLauncher() {
        val intent = Intent(Intent.ACTION_MAIN).apply {
            addCategory(Intent.CATEGORY_HOME)
        }
        val launchers = packageManager.queryIntentActivities(intent, 0)
            .filter { it.activityInfo.packageName != packageName }

        if (launchers.size == 1) {
            val ri = launchers[0]
            val launchIntent = Intent(Intent.ACTION_MAIN).apply {
                addCategory(Intent.CATEGORY_HOME)
                component = ComponentName(ri.activityInfo.packageName, ri.activityInfo.name)
                flags = Intent.FLAG_ACTIVITY_NEW_TASK
            }
            startActivity(launchIntent)
        } else if (launchers.isNotEmpty()) {
            startActivity(Intent.createChooser(intent, null))
        } else {
            Toast.makeText(this, "No other launcher found", Toast.LENGTH_SHORT).show()
        }
    }
}
