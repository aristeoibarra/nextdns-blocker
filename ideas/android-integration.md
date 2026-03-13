# Android Integration: ndb remote app blocking

## Problem

`ndb block youtube.com` blocks YouTube everywhere EXCEPT Android apps:
- DNS blocking (NextDNS) works for browsers but Android apps bypass it (cached IPs, DoH)
- No equivalent to Mac's app_blocker (rename .app) on Android
- `pm disable-user` via SSH/Termux is fragile — Android kills Termux in background
- SSH requires same network

## Solution

Minimal Android app (Device Owner) controlled remotely by ndb via Firebase.

```
ndb block youtube.com
  ├→ NextDNS API (DNS blocking — all devices)
  ├→ Mac app_blocker (rename .app + killall)
  ├→ Mac hosts_blocker (/etc/hosts)
  ├→ Mac browser_blocker (close tabs)
  ├→ Firebase RTDB: PUT desired state          ← NEW
  └→ FCM: send high-priority push              ← NEW
                                                    │
                              Android app receives FCM push
                                                    │
                              ├→ Read desired state from Firebase RTDB
                              ├→ Diff vs local state
                              └→ dpm.setApplicationHidden(youtube, true)
                                   App DISAPPEARS. Can't re-enable from Settings.
```

## Architecture

### Why Firebase (and not SSH, MQTT, ntfy, WebSocket)

| Transport    | Real-time | Survives Doze | Works off-network | Reliable |
|-------------|-----------|---------------|-------------------|----------|
| SSH/Termux  | Yes       | No            | No                | No       |
| ntfy.sh     | Yes       | Partial       | Yes               | Partial  |
| MQTT        | Yes       | No            | Yes               | Partial  |
| WebSocket   | Yes       | No            | Yes               | No       |
| **FCM**     | **Yes**   | **Yes**       | **Yes**            | **Yes**  |

FCM is part of Google Play Services (system process, never killed by Android).
High-priority data messages bypass Doze mode. Near-instant delivery.

### Why Device Owner (not Device Admin)

| Capability                          | Device Admin | Device Owner |
|------------------------------------|-------------|-------------|
| `setApplicationHidden()`           | Yes         | Yes         |
| App disappears from launcher       | Yes         | Yes         |
| App disappears from Settings       | No          | **Yes**     |
| Can be deactivated from Settings   | **Yes** (2 taps) | **No** |
| How to remove                      | Settings    | **ADB only or factory reset** |
| Setup                              | UI prompt   | `adb shell dpm set-device-owner` (once) |

Device Owner = what enterprises use for MDM. Once set, the app controls which apps are visible. To remove it you need a computer + ADB. That's real friction.

### Three delivery layers (commands never lost)

```
1. FCM push (immediate)       → App receives, executes in < 1 second
2. WorkManager (every 15 min) → Reads RTDB state, corrects drift
3. BootReceiver               → Full sync on device boot
```

If FCM fails → WorkManager catches it within 15 min.
If WorkManager fails → BootReceiver catches it on next reboot.
State lives in Firebase RTDB (cloud), not on the phone.

### Bypass analysis

| Bypass attempt                    | Result                                    |
|----------------------------------|------------------------------------------|
| Open YouTube from launcher       | Not there, it's hidden                    |
| Search YouTube in Settings→Apps  | Not visible (Device Owner)                |
| Deactivate Device Admin          | Can't (Device Owner)                      |
| Uninstall ndb-blocker            | Can't (Device Owner)                      |
| Kill the app                     | FCM wakes it, WorkManager re-runs         |
| Reboot phone                     | BootReceiver re-syncs                     |
| Enable app via ADB              | WorkManager re-disables within 15 min     |
| Remove Device Owner via ADB     | **Only real bypass** — needs a computer   |
| Factory reset                    | Works, but you lose everything            |

## Firebase Cost

Spark plan (free). No credit card required.

| Resource             | Free limit   | Estimated usage |
|---------------------|-------------|-----------------|
| RTDB storage        | 1 GB        | < 1 KB          |
| RTDB bandwidth      | 10 GB/month | < 1 MB/month    |
| FCM messages        | Unlimited   | ~50/day max     |
| Auth                | 10K/month   | 1 user          |

Will never hit paid tier. Sending 200-byte JSONs a few times per day.

## Firebase RTDB Schema

```json
{
  "devices": {
    "android_pixel": {
      "blocked_packages": {
        "com.google.android.youtube": {
          "domain": "youtube.com",
          "blocked_at": 1710000000,
          "unblock_at": null
        },
        "com.zhiliaoapp.musically": {
          "domain": "tiktok.com",
          "blocked_at": 1710000000,
          "unblock_at": 1710003600
        }
      },
      "last_sync": 1710000000,
      "fcm_token": "..."
    }
  }
}
```

- `unblock_at: null` = blocked indefinitely
- `unblock_at: timestamp` = temporary unblock (e.g., `ndb unblock youtube.com -d 30m`)
- `last_sync` = last time Android app synced (for monitoring)

## Firebase RTDB Security Rules

```json
{
  "rules": {
    "devices": {
      "$device_id": {
        ".read": "auth != null",
        ".write": "auth != null"
      }
    }
  }
}
```

Use Firebase Auth with a service account for ndb (Mac) and anonymous auth or custom token for the Android app.

## Implementation

### Part 1: Android App (~200 lines Kotlin)

```
com.ndb.blocker/
├── NdbApp.kt              // Application: init Firebase
├── NdbDeviceAdmin.kt       // DeviceAdminReceiver (empty, enables privileges)
├── NdbFcmService.kt        // Receives FCM → calls BlockerEngine.sync()
├── NdbBootReceiver.kt      // BOOT_COMPLETED → calls BlockerEngine.sync()
├── NdbSyncWorker.kt        // WorkManager every 15m → calls BlockerEngine.sync()
├── BlockerEngine.kt        // Core: read RTDB, diff, setApplicationHidden()
└── MainActivity.kt         // Minimal: status + Device Owner setup instructions
```

#### BlockerEngine.kt (core logic)

```kotlin
class BlockerEngine(private val context: Context) {
    private val dpm = context.getSystemService(DevicePolicyManager::class.java)
    private val admin = ComponentName(context, NdbDeviceAdmin::class.java)
    private val db = FirebaseDatabase.getInstance()

    fun sync() {
        val ref = db.getReference("devices/android_pixel/blocked_packages")
        ref.get().addOnSuccessListener { snapshot ->
            snapshot.children.forEach { child ->
                val pkg = child.key ?: return@forEach
                val unblockAt = child.child("unblock_at").getValue(Long::class.java)
                val now = System.currentTimeMillis() / 1000

                val shouldBlock = unblockAt == null || unblockAt > now

                try {
                    val isHidden = dpm.isApplicationHidden(admin, pkg)
                    if (shouldBlock && !isHidden) {
                        dpm.setApplicationHidden(admin, pkg, true)
                    } else if (!shouldBlock && isHidden) {
                        dpm.setApplicationHidden(admin, pkg, false)
                        // Remove from RTDB after unblock
                        child.ref.removeValue()
                    }
                } catch (e: Exception) {
                    // Package not installed, skip
                }
            }

            // Update last_sync timestamp
            db.getReference("devices/android_pixel/last_sync")
                .setValue(System.currentTimeMillis() / 1000)
        }
    }
}
```

#### NdbFcmService.kt

```kotlin
class NdbFcmService : FirebaseMessagingService() {
    override fun onMessageReceived(message: RemoteMessage) {
        if (message.data["action"] == "sync") {
            BlockerEngine(applicationContext).sync()
        }
    }

    override fun onNewToken(token: String) {
        // Send token to Firebase RTDB so Mac can target this device
        FirebaseDatabase.getInstance()
            .getReference("devices/android_pixel/fcm_token")
            .setValue(token)
    }
}
```

#### NdbSyncWorker.kt

```kotlin
class NdbSyncWorker(ctx: Context, params: WorkerParameters) : Worker(ctx, params) {
    override fun doWork(): Result {
        BlockerEngine(applicationContext).sync()
        return Result.success()
    }
}

// Scheduled in NdbApp.kt:
// WorkManager.getInstance(this).enqueueUniquePeriodicWork(
//     "ndb-sync",
//     ExistingPeriodicWorkPolicy.KEEP,
//     PeriodicWorkRequestBuilder<NdbSyncWorker>(15, TimeUnit.MINUTES).build()
// )
```

#### NdbBootReceiver.kt

```kotlin
class NdbBootReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        if (intent.action == Intent.ACTION_BOOT_COMPLETED) {
            BlockerEngine(context).sync()
        }
    }
}
```

#### NdbDeviceAdmin.kt

```kotlin
class NdbDeviceAdmin : DeviceAdminReceiver() {
    // Empty — just enables Device Admin/Owner privileges
}
```

#### AndroidManifest.xml (key parts)

```xml
<uses-permission android:name="android.permission.RECEIVE_BOOT_COMPLETED" />
<uses-permission android:name="android.permission.INTERNET" />

<application>
    <receiver android:name=".NdbDeviceAdmin"
        android:permission="android.permission.BIND_DEVICE_ADMIN">
        <meta-data android:name="android.app.device_admin"
            android:resource="@xml/device_admin" />
        <intent-filter>
            <action android:name="android.app.action.DEVICE_ADMIN_ENABLED" />
        </intent-filter>
    </receiver>

    <receiver android:name=".NdbBootReceiver"
        android:exported="true">
        <intent-filter>
            <action android:name="android.intent.action.BOOT_COMPLETED" />
        </intent-filter>
    </receiver>

    <service android:name=".NdbFcmService"
        android:exported="false">
        <intent-filter>
            <action android:name="com.google.firebase.MESSAGING_EVENT" />
        </intent-filter>
    </service>
</application>
```

#### res/xml/device_admin.xml

```xml
<device-admin>
    <uses-policies />
</device-admin>
```

### Part 2: ndb Rust changes (~100 lines)

#### New module: src/remote/mod.rs

```rust
pub mod firebase;
pub mod fcm;
pub mod android_mappings;
```

#### src/remote/firebase.rs

```rust
use crate::common::keychain;
use serde_json::json;

pub fn set_package_blocked(
    package: &str,
    domain: &str,
    blocked: bool,
    unblock_at: Option<i64>,
) -> Result<(), Box<dyn std::error::Error>> {
    let rtdb_url = keychain::get_secret("firebase_rtdb_url")?;
    let auth_token = keychain::get_secret("firebase_auth_token")?;

    if blocked {
        let url = format!(
            "{}/devices/android_pixel/blocked_packages/{}.json?auth={}",
            rtdb_url, package, auth_token
        );
        ureq::put(&url).send_json(&json!({
            "domain": domain,
            "blocked_at": chrono::Utc::now().timestamp(),
            "unblock_at": unblock_at,
        }))?;
    } else {
        let url = format!(
            "{}/devices/android_pixel/blocked_packages/{}.json?auth={}",
            rtdb_url, package, auth_token
        );
        ureq::delete(&url).call()?;
    }

    Ok(())
}
```

#### src/remote/fcm.rs

```rust
use crate::common::keychain;
use serde_json::json;

pub fn send_sync_push() -> Result<(), Box<dyn std::error::Error>> {
    let server_key = keychain::get_secret("fcm_server_key")?;
    let device_token = keychain::get_secret("android_fcm_token")?;

    ureq::post("https://fcm.googleapis.com/fcm/send")
        .header("Authorization", &format!("key={}", server_key))
        .header("Content-Type", "application/json")
        .send_json(&json!({
            "to": device_token,
            "priority": "high",
            "data": {
                "action": "sync"
            }
        }))?;

    Ok(())
}
```

#### src/remote/android_mappings.rs

```rust
/// Maps domains to Android package names.
/// Equivalent of app_blocker::mappings::KNOWN_MAPPINGS but for Android.
pub const ANDROID_PACKAGES: &[(&str, &str)] = &[
    ("youtube.com", "com.google.android.youtube"),
    ("tiktok.com", "com.zhiliaoapp.musically"),
    ("instagram.com", "com.instagram.android"),
    ("twitter.com", "com.twitter.android"),
    ("x.com", "com.twitter.android"),
    ("facebook.com", "com.facebook.katana"),
    ("whatsapp.com", "com.whatsapp"),
    ("netflix.com", "com.netflix.mediaclient"),
    ("reddit.com", "com.reddit.frontpage"),
    ("snapchat.com", "com.snapchat.android"),
    ("twitch.tv", "tv.twitch.android.app"),
    ("discord.com", "com.discord"),
    ("telegram.org", "org.telegram.messenger"),
    ("pinterest.com", "com.pinterest"),
    ("linkedin.com", "com.linkedin.android"),
    ("spotify.com", "com.spotify.music"),
    ("amazon.com", "com.amazon.mShop.android.shopping"),
    ("ebay.com", "com.ebay.mobile"),
    ("tumblr.com", "com.tumblr"),
    ("vimeo.com", "com.vimeo.android.videoapp"),
];

pub fn get_android_package(domain: &str) -> Option<&'static str> {
    ANDROID_PACKAGES
        .iter()
        .find(|(d, _)| *d == domain)
        .map(|(_, pkg)| *pkg)
}
```

#### Changes to handlers/block.rs (pseudocode)

```rust
// After existing Mac blocking logic:
if let Some(pkg) = remote::android_mappings::get_android_package(domain) {
    if let Err(e) = remote::firebase::set_package_blocked(pkg, domain, true, None) {
        // Best-effort: log but don't fail the command
        eprintln!("Warning: failed to sync to Android: {}", e);
    }
    if let Err(e) = remote::fcm::send_sync_push() {
        eprintln!("Warning: failed to send FCM push: {}", e);
    }
}
```

#### Changes to handlers/unblock.rs (pseudocode)

```rust
// After existing Mac unblocking logic:
if let Some(pkg) = remote::android_mappings::get_android_package(domain) {
    let unblock_at = duration.map(|d| (Utc::now() + d).timestamp());
    if unblock_at.is_some() {
        // Temporary unblock: update with expiry
        remote::firebase::set_package_blocked(pkg, domain, true, unblock_at)?;
    } else {
        // Permanent unblock: remove
        remote::firebase::set_package_blocked(pkg, domain, false, None)?;
    }
    remote::fcm::send_sync_push()?;
}
```

### Part 3: Setup (one-time)

#### 1. Firebase project

```bash
# Install Firebase CLI (npm)
npm install -g firebase-tools
firebase login
firebase projects:create ndb-blocker
firebase database:instances:create ndb-blocker --location us-central1
```

Or via console: https://console.firebase.google.com → Create project → Enable Realtime Database + Cloud Messaging.

#### 2. Android app

```bash
# Build and install APK
cd android/ndb-blocker
./gradlew assembleDebug
adb install app/build/outputs/apk/debug/app-debug.apk

# Set as Device Owner (phone must have no accounts, or remove them temporarily)
adb shell dpm set-device-owner com.ndb.blocker/.NdbDeviceAdmin

# Verify
adb shell dpm list-owners
```

NOTE: To set Device Owner, the phone must have NO accounts (Google, Samsung, etc.) configured. Remove them temporarily, set Device Owner, then re-add them. This is a one-time setup.

Alternative: If removing accounts is not feasible, use `adb shell dpm set-profile-owner` instead (slightly less restrictive but still effective).

#### 3. ndb config

```bash
# Store Firebase credentials in Keychain
ndb config set-secret firebase_rtdb_url "https://ndb-blocker-default-rtdb.firebaseio.com"
ndb config set-secret firebase_auth_token "<database-secret-or-service-account-token>"
ndb config set-secret fcm_server_key "<server-key-from-firebase-console>"

# Android FCM token is auto-registered by the app on first launch
# It writes to RTDB at devices/android_pixel/fcm_token
# ndb reads it from there, or you can set it manually:
ndb config set-secret android_fcm_token "<token>"
```

## Scalability

This architecture naturally extends to:

- **Multiple Android devices**: Add device IDs to RTDB (`devices/{device_id}/`)
- **iOS/iPad**: Use MDM profiles (different mechanism, same Firebase state)
- **Schedules**: `unblock_at` already supports time-based unblocking
- **New apps**: Just add to ANDROID_PACKAGES mapping
- **Bidirectional status**: Android reports to RTDB, Mac reads with `ndb status --android`
- **Notifications on Android**: FCM can carry notification payloads too

## Implementation Order

1. **Firebase project setup** (10 min)
2. **Android app** — BlockerEngine + FCM + WorkManager + DeviceAdmin (~200 lines Kotlin)
3. **ndb remote module** — firebase.rs + fcm.rs + android_mappings.rs (~100 lines Rust)
4. **Wire into block/unblock handlers** (~20 lines changes)
5. **Test**: `ndb block youtube.com` → verify YouTube disappears from Android
6. **Device Owner setup** via ADB (5 min)
