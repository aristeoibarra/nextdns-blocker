package com.ndb.blocker

import android.os.Bundle
import androidx.appcompat.app.AppCompatActivity
import androidx.fragment.app.Fragment
import com.google.android.material.bottomnavigation.BottomNavigationView

class MainActivity : AppCompatActivity() {

    lateinit var engine: BlockerEngine
        private set

    private val statusFragment = StatusFragment()
    private val blockedFragment = BlockedFragment()
    private val allowedFragment = AllowedFragment()
    private val dnsFragment = DnsFragment()
    private val settingsFragment = SettingsFragment()
    private var activeFragment: Fragment = statusFragment

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)
        engine = BlockerEngine(this)

        // Add all fragments, hide non-active
        supportFragmentManager.beginTransaction()
            .add(R.id.fragmentContainer, settingsFragment, "settings").hide(settingsFragment)
            .add(R.id.fragmentContainer, dnsFragment, "dns").hide(dnsFragment)
            .add(R.id.fragmentContainer, allowedFragment, "allowed").hide(allowedFragment)
            .add(R.id.fragmentContainer, blockedFragment, "blocked").hide(blockedFragment)
            .add(R.id.fragmentContainer, statusFragment, "status")
            .commit()

        val bottomNav = findViewById<BottomNavigationView>(R.id.bottomNavigation)
        bottomNav.setOnItemSelectedListener { item ->
            val selected: Fragment = when (item.itemId) {
                R.id.nav_status -> statusFragment
                R.id.nav_blocked -> blockedFragment
                R.id.nav_allowed -> allowedFragment
                R.id.nav_dns -> dnsFragment
                R.id.nav_settings -> settingsFragment
                else -> statusFragment
            }
            if (selected != activeFragment) {
                supportFragmentManager.beginTransaction()
                    .hide(activeFragment)
                    .show(selected)
                    .commit()
                activeFragment = selected
            }
            true
        }
    }

    fun onSyncComplete() {
        statusFragment.refreshStatus()
        blockedFragment.loadData()
        allowedFragment.loadData()
        dnsFragment.loadData()
    }
}
