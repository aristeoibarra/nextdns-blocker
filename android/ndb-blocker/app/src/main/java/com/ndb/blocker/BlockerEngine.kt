package com.ndb.blocker

import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.util.Log
import com.google.firebase.database.FirebaseDatabase

class BlockerEngine(private val context: Context) {

    companion object {
        private const val TAG = "BlockerEngine"
        private const val DEVICE_ID = "android_pixel"
    }

    private val db = FirebaseDatabase.getInstance()

    fun sync() {
        reportInstalledApps()

        val ref = db.getReference("devices/$DEVICE_ID/blocked_packages")
        ref.get().addOnSuccessListener { snapshot ->
            val now = System.currentTimeMillis() / 1000
            val blocked = mutableSetOf<String>()

            for (child in snapshot.children) {
                val encodedKey = child.key ?: continue
                // CLI encodes '.' as '~' in Firebase keys; decode back
                val pkg = encodedKey.replace('~', '.')
                val unblockAt = child.child("unblock_at").getValue(Long::class.java)
                val shouldBlock = unblockAt == null || unblockAt > now

                if (shouldBlock) {
                    blocked.add(pkg)
                } else {
                    // Expired, remove from Firebase
                    child.ref.removeValue()
                    Log.i(TAG, "Expired, unblocked: $pkg")
                }
            }

            NdbAccessibilityService.updateBlockedPackages(context, blocked)

            db.getReference("devices/$DEVICE_ID/last_sync")
                .setValue(System.currentTimeMillis() / 1000)

            Log.i(TAG, "Sync complete, ${blocked.size} packages blocked")
        }.addOnFailureListener { e ->
            Log.e(TAG, "Failed to read blocked_packages", e)
        }
    }

    fun reportInstalledApps() {
        val pm = context.packageManager
        val launcherIntent = Intent(Intent.ACTION_MAIN).apply {
            addCategory(Intent.CATEGORY_LAUNCHER)
        }
        val launchable = pm.queryIntentActivities(launcherIntent, 0)
            .map { it.activityInfo.packageName }
            .toSet()

        val ref = db.getReference("devices/$DEVICE_ID/installed_packages")
        var count = 0

        for (pkg in launchable) {
            if (pkg == context.packageName) continue
            try {
                val info = pm.getApplicationInfo(pkg, 0)
                val label = pm.getApplicationLabel(info).toString()
                val version = try {
                    pm.getPackageInfo(pkg, 0).versionName ?: "unknown"
                } catch (_: PackageManager.NameNotFoundException) {
                    "unknown"
                }
                // Firebase keys can't contain '.', encode as '~'
                val encodedPkg = pkg.replace('.', '~')
                ref.child(encodedPkg).setValue(mapOf(
                    "label" to label,
                    "version" to version,
                    "package" to pkg
                ))
                count++
            } catch (_: PackageManager.NameNotFoundException) {
                continue
            }
        }

        Log.i(TAG, "Reported $count installed apps")
    }

    fun getBlockedCount(callback: (Int) -> Unit) {
        val ref = db.getReference("devices/$DEVICE_ID/blocked_packages")
        ref.get().addOnSuccessListener { snapshot ->
            callback(snapshot.childrenCount.toInt())
        }.addOnFailureListener {
            callback(0)
        }
    }

    fun getLastSync(callback: (Long?) -> Unit) {
        val ref = db.getReference("devices/$DEVICE_ID/last_sync")
        ref.get().addOnSuccessListener { snapshot ->
            callback(snapshot.getValue(Long::class.java))
        }.addOnFailureListener {
            callback(null)
        }
    }

    fun getSyncState(callback: (SyncState?) -> Unit) {
        val ref = db.getReference("devices/$DEVICE_ID/sync_state")
        ref.get().addOnSuccessListener { snapshot ->
            if (!snapshot.exists()) {
                callback(null)
                return@addOnSuccessListener
            }

            val categories = mutableListOf<String>()
            for (child in snapshot.child("categories").children) {
                child.getValue(String::class.java)?.let { categories.add(it) }
            }

            val blocked = mutableListOf<AppEntry>()
            for (child in snapshot.child("blocked").children) {
                val encodedKey = child.key ?: continue
                val pkg = encodedKey.replace('~', '.')
                val name = child.child("name").getValue(String::class.java) ?: pkg
                val reason = child.child("reason").getValue(String::class.java) ?: ""
                blocked.add(AppEntry(pkg, name, reason))
            }

            val allowed = mutableListOf<AppEntry>()
            for (child in snapshot.child("allowed").children) {
                val encodedKey = child.key ?: continue
                val pkg = encodedKey.replace('~', '.')
                val name = child.child("name").getValue(String::class.java) ?: pkg
                val reason = child.child("reason").getValue(String::class.java) ?: ""
                allowed.add(AppEntry(pkg, name, reason))
            }

            val totalBlocked = snapshot.child("total_blocked").getValue(Int::class.java) ?: blocked.size
            val totalAllowed = snapshot.child("total_allowed").getValue(Int::class.java) ?: allowed.size
            val syncedAt = snapshot.child("synced_at").getValue(Long::class.java) ?: 0L

            callback(SyncState(categories, blocked, allowed, totalBlocked, totalAllowed, syncedAt))
        }.addOnFailureListener {
            callback(null)
        }
    }

    fun getDnsState(callback: (DnsState?) -> Unit) {
        val ref = db.getReference("devices/$DEVICE_ID/dns_state")
        ref.get().addOnSuccessListener { snapshot ->
            if (!snapshot.exists()) {
                callback(null)
                return@addOnSuccessListener
            }

            val customCategories = mutableListOf<DnsCategory>()
            for (child in snapshot.child("custom_categories").children) {
                val name = child.key ?: continue
                val description = child.child("description").getValue(String::class.java)
                val count = child.child("count").getValue(Int::class.java) ?: 0
                val domains = mutableListOf<String>()
                for (d in child.child("domains").children) {
                    d.getValue(String::class.java)?.let { domains.add(it) }
                }
                customCategories.add(DnsCategory(name, description, domains, count))
            }

            val uncategorized = mutableListOf<DnsDomain>()
            for (child in snapshot.child("uncategorized").children) {
                val domain = child.child("domain").getValue(String::class.java) ?: continue
                val description = child.child("description").getValue(String::class.java)
                uncategorized.add(DnsDomain(domain, description))
            }

            val allowedDomains = mutableListOf<DnsDomain>()
            for (child in snapshot.child("allowed_domains").children) {
                val domain = child.child("domain").getValue(String::class.java) ?: continue
                val description = child.child("description").getValue(String::class.java)
                allowedDomains.add(DnsDomain(domain, description))
            }

            val totalBlocked = snapshot.child("total_blocked_domains").getValue(Int::class.java) ?: 0
            val totalAllowed = snapshot.child("total_allowed_domains").getValue(Int::class.java) ?: 0
            val syncedAt = snapshot.child("synced_at").getValue(Long::class.java) ?: 0L

            callback(DnsState(customCategories, uncategorized, allowedDomains, totalBlocked, totalAllowed, syncedAt))
        }.addOnFailureListener {
            callback(null)
        }
    }
}
