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
import android.widget.TextView
import com.google.android.material.bottomsheet.BottomSheetDialog
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
            onLongPress = { app, _ -> showBottomSheet(app) }
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

        // Swipe from right to left → go back to home
        gestureDetector = GestureDetector(this, object : GestureDetector.SimpleOnGestureListener() {
            override fun onFling(e1: MotionEvent?, e2: MotionEvent, vX: Float, vY: Float): Boolean {
                if (e1 == null) return false
                val dx = e2.x - e1.x
                val dy = e2.y - e1.y
                if (dx < -80 && abs(dx) > abs(dy)) {
                    goBack()
                    return true
                }
                return false
            }
        })

        loadApps()
    }

    override fun dispatchTouchEvent(ev: MotionEvent): Boolean {
        gestureDetector.onTouchEvent(ev)
        return super.dispatchTouchEvent(ev)
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
        overridePendingTransition(R.anim.slide_in_right, R.anim.slide_out_left)
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

    private fun showBottomSheet(app: AppModel) {
        val dialog = BottomSheetDialog(this, R.style.Theme_NdbBlocker_BottomSheet)
        val view = layoutInflater.inflate(R.layout.bottom_sheet_app_actions, null)

        view.findViewById<TextView>(R.id.tvSheetTitle).text = app.label

        view.findViewById<TextView>(R.id.btnAddHome).setOnClickListener {
            prefs.addFavorite(app.packageName)
            dialog.dismiss()
        }

        view.findViewById<TextView>(R.id.btnHide).setOnClickListener {
            prefs.hidePackage(app.packageName)
            loadApps()
            dialog.dismiss()
        }

        dialog.setContentView(view)
        dialog.show()
    }
}
