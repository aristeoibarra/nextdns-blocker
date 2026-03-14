package com.ndb.blocker

import android.content.Intent
import android.os.Bundle
import android.text.Editable
import android.text.TextWatcher
import android.view.GestureDetector
import android.view.MotionEvent
import android.view.View
import android.widget.EditText
import android.widget.ImageView
import android.widget.PopupMenu
import androidx.appcompat.app.AppCompatActivity
import androidx.recyclerview.widget.LinearLayoutManager
import androidx.recyclerview.widget.RecyclerView
import kotlin.math.abs

class DrawerActivity : AppCompatActivity() {

    private lateinit var prefs: LauncherPrefs
    private lateinit var adapter: DrawerAdapter
    private lateinit var gestureDetector: GestureDetector

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_drawer)

        prefs = LauncherPrefs(this)

        adapter = DrawerAdapter(
            onTap = { pkg -> launchApp(pkg) },
            onLongPress = { app, anchor -> showPopup(app, anchor) }
        )

        val rv = findViewById<RecyclerView>(R.id.rvApps)
        rv.layoutManager = LinearLayoutManager(this)
        rv.adapter = adapter

        val etSearch = findViewById<EditText>(R.id.etSearch)
        etSearch.addTextChangedListener(object : TextWatcher {
            override fun beforeTextChanged(s: CharSequence?, start: Int, count: Int, after: Int) {}
            override fun onTextChanged(s: CharSequence?, start: Int, before: Int, count: Int) {
                adapter.filter.filter(s)
            }
            override fun afterTextChanged(s: Editable?) {}
        })

        findViewById<ImageView>(R.id.btnSettings).setOnClickListener {
            startActivity(Intent(this, MainActivity::class.java))
        }

        findViewById<ImageView>(R.id.btnHidden).setOnClickListener {
            startActivity(Intent(this, HiddenAppsActivity::class.java))
        }

        // Swipe right to go back
        gestureDetector = GestureDetector(this, object : GestureDetector.SimpleOnGestureListener() {
            override fun onFling(e1: MotionEvent?, e2: MotionEvent, vX: Float, vY: Float): Boolean {
                if (e1 == null) return false
                val dx = e2.x - e1.x
                val dy = e2.y - e1.y
                if (dx > 150 && abs(dx) > abs(dy)) {
                    goBack()
                    return true
                }
                return false
            }
        })

        rv.addOnItemTouchListener(object : RecyclerView.OnItemTouchListener {
            override fun onInterceptTouchEvent(rv: RecyclerView, e: MotionEvent): Boolean {
                gestureDetector.onTouchEvent(e)
                return false
            }
            override fun onTouchEvent(rv: RecyclerView, e: MotionEvent) {}
            override fun onRequestDisallowInterceptTouchEvent(disallowIntercept: Boolean) {}
        })

        loadApps()
    }

    override fun onResume() {
        super.onResume()
        loadApps()
    }

    @Deprecated("Deprecated in Java")
    override fun onBackPressed() {
        goBack()
    }

    private fun goBack() {
        finish()
        overridePendingTransition(R.anim.slide_in_left, R.anim.slide_out_right)
    }

    private fun loadApps() {
        val blocked = NdbAccessibilityService.getBlockedPackages(this)
        val hidden = prefs.getHiddenPackages()
        val apps = queryLaunchableApps(this)
            .filter { it.packageName !in blocked && it.packageName !in hidden }
        adapter.submit(apps)
    }

    private fun launchApp(pkg: String) {
        val intent = packageManager.getLaunchIntentForPackage(pkg) ?: return
        startActivity(intent)
    }

    private fun showPopup(app: AppModel, anchor: View) {
        val popup = PopupMenu(this, anchor)
        popup.menu.add(0, 1, 0, getString(R.string.launcher_add_to_home))
        popup.menu.add(0, 2, 1, getString(R.string.launcher_hide))
        popup.setOnMenuItemClickListener { item ->
            when (item.itemId) {
                1 -> {
                    prefs.addFavorite(app.packageName)
                    true
                }
                2 -> {
                    prefs.hidePackage(app.packageName)
                    loadApps()
                    true
                }
                else -> false
            }
        }
        popup.show()
    }
}
