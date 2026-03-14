package com.ndb.blocker

import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Bundle
import android.widget.Button
import android.widget.TextView
import androidx.appcompat.app.AppCompatActivity

class BlockedActivity : AppCompatActivity() {

    companion object {
        private const val EXTRA_PACKAGE = "blocked_package"

        fun launch(context: Context, packageName: String) {
            val intent = Intent(context, BlockedActivity::class.java).apply {
                putExtra(EXTRA_PACKAGE, packageName)
                addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP)
            }
            context.startActivity(intent)
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_blocked)

        val pkg = intent.getStringExtra(EXTRA_PACKAGE) ?: ""

        val appLabel = try {
            val info = packageManager.getApplicationInfo(pkg, 0)
            packageManager.getApplicationLabel(info).toString()
        } catch (_: PackageManager.NameNotFoundException) {
            pkg
        }

        findViewById<TextView>(R.id.tvBlockedApp).text = appLabel
        findViewById<TextView>(R.id.tvBlockedPackage).text = pkg

        findViewById<Button>(R.id.btnGoHome).setOnClickListener {
            val home = Intent(Intent.ACTION_MAIN).apply {
                addCategory(Intent.CATEGORY_HOME)
                flags = Intent.FLAG_ACTIVITY_NEW_TASK
            }
            startActivity(home)
            finish()
        }
    }

    override fun onBackPressed() {
        super.onBackPressed()
        val home = Intent(Intent.ACTION_MAIN).apply {
            addCategory(Intent.CATEGORY_HOME)
            flags = Intent.FLAG_ACTIVITY_NEW_TASK
        }
        startActivity(home)
        finish()
    }
}
