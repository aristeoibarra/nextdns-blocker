use nextdns_blocker::common::time::now_unix;
use nextdns_blocker::db::android;
use nextdns_blocker::db::apps;
use nextdns_blocker::db::audit;
use nextdns_blocker::db::categories;
use nextdns_blocker::db::domains;
use nextdns_blocker::db::nextdns;
use nextdns_blocker::db::pending;

use nextdns_blocker::db::Database;

/// Helper: create an in-memory database ready for testing.
fn setup_db() -> Database {
    Database::open_memory().expect("failed to open in-memory database")
}

// ---------------------------------------------------------------------------
// 1. Open in-memory DB and verify it works
// ---------------------------------------------------------------------------
#[test]
fn test_open_memory_and_migrate() {
    let db = setup_db();

    // The database should be usable right after creation.
    let count = db
        .with_conn(|conn| {
            conn.query_row(
                "SELECT COUNT(*) FROM schema_migrations",
                [],
                |row| row.get::<_, i64>(0),
            )
        })
        .expect("failed to query schema_migrations");

    // At least one migration must have been applied.
    assert!(count > 0, "expected at least one applied migration, got {count}");
}

// ---------------------------------------------------------------------------
// 2. Blocked domain CRUD
// ---------------------------------------------------------------------------
#[test]
fn test_blocked_domain_crud() {
    let db = setup_db();

    db.with_conn(|conn| {
        // Add
        let id = domains::add_blocked(conn, "example.com", Some("test"), None, None)?;
        assert!(id > 0);

        // List (active only)
        let list = domains::list_blocked(conn, true)?;
        assert_eq!(list.len(), 1);
        assert_eq!(list[0].domain, "example.com");
        assert!(list[0].active);

        // is_blocked
        assert!(domains::is_blocked(conn, "example.com")?);
        assert!(!domains::is_blocked(conn, "other.com")?);

        // count
        assert_eq!(domains::count_blocked(conn)?, 1);

        // get_blocked
        let entry = domains::get_blocked(conn, "example.com")?;
        assert!(entry.is_some());
        let entry = entry.unwrap();
        assert_eq!(entry.description.as_deref(), Some("test"));

        // Remove
        let removed = domains::remove_blocked(conn, "example.com")?;
        assert!(removed);

        // Verify removed
        assert!(!domains::is_blocked(conn, "example.com")?);
        assert_eq!(domains::count_blocked(conn)?, 0);

        // Remove non-existent returns false
        let removed = domains::remove_blocked(conn, "example.com")?;
        assert!(!removed);

        Ok(())
    })
    .expect("blocked domain CRUD failed");
}

// ---------------------------------------------------------------------------
// 3. Allowed domain CRUD
// ---------------------------------------------------------------------------
#[test]
fn test_allowed_domain_crud() {
    let db = setup_db();

    db.with_conn(|conn| {
        // Add
        let id = domains::add_allowed(conn, "safe.com", Some("trusted"), None)?;
        assert!(id > 0);

        // List
        let list = domains::list_allowed(conn, true)?;
        assert_eq!(list.len(), 1);
        assert_eq!(list[0].domain, "safe.com");
        assert!(list[0].active);

        // is_allowed
        assert!(domains::is_allowed(conn, "safe.com")?);
        assert!(!domains::is_allowed(conn, "unsafe.com")?);

        // count
        assert_eq!(domains::count_allowed(conn)?, 1);

        // get_allowed
        let entry = domains::get_allowed(conn, "safe.com")?;
        assert!(entry.is_some());
        assert_eq!(entry.unwrap().description.as_deref(), Some("trusted"));

        // Remove
        let removed = domains::remove_allowed(conn, "safe.com")?;
        assert!(removed);

        assert!(!domains::is_allowed(conn, "safe.com")?);
        assert_eq!(domains::count_allowed(conn)?, 0);

        Ok(())
    })
    .expect("allowed domain CRUD failed");
}

// ---------------------------------------------------------------------------
// 4. Duplicate blocked domain
// ---------------------------------------------------------------------------
#[test]
fn test_duplicate_blocked_domain() {
    let db = setup_db();

    db.with_conn(|conn| {
        // Insert the domain the first time.
        domains::add_blocked(conn, "dup.com", Some("first"), None, None)?;

        // Insert the same domain again -- should succeed via ON CONFLICT DO UPDATE.
        domains::add_blocked(conn, "dup.com", Some("second"), None, None)?;

        // Only one row should exist.
        let list = domains::list_blocked(conn, false)?;
        let matching: Vec<_> = list.iter().filter(|d| d.domain == "dup.com").collect();
        assert_eq!(matching.len(), 1, "duplicate insert should not create a second row");

        // The description should have been updated to the latest value.
        assert_eq!(matching[0].description.as_deref(), Some("second"));

        Ok(())
    })
    .expect("duplicate blocked domain test failed");
}

// ---------------------------------------------------------------------------
// 5. Category CRUD
// ---------------------------------------------------------------------------
#[test]
fn test_category_crud() {
    let db = setup_db();

    db.with_conn(|conn| {
        // Create
        let id = categories::create_category(conn, "social", Some("Social media"), None)?;
        assert!(id > 0);

        // List
        let list = categories::list_categories(conn)?;
        assert_eq!(list.len(), 1);
        assert_eq!(list[0].name, "social");

        // Get by name
        let cat = categories::get_category(conn, "social")?;
        assert!(cat.is_some());
        let cat = cat.unwrap();
        assert_eq!(cat.description.as_deref(), Some("Social media"));
        // Get non-existent
        assert!(categories::get_category(conn, "nonexistent")?.is_none());

        // Delete
        let deleted = categories::delete_category(conn, "social")?;
        assert!(deleted);

        assert!(categories::get_category(conn, "social")?.is_none());
        assert!(categories::list_categories(conn)?.is_empty());

        Ok(())
    })
    .expect("category CRUD failed");
}

// ---------------------------------------------------------------------------
// 6. Category domains
// ---------------------------------------------------------------------------
#[test]
fn test_category_domains() {
    let db = setup_db();

    db.with_conn(|conn| {
        // Create a category first
        categories::create_category(conn, "gaming", Some("Game sites"), None)?;

        // Add domains
        assert!(categories::add_domain_to_category(conn, "gaming", "steam.com")?);
        assert!(categories::add_domain_to_category(conn, "gaming", "epic.com")?);

        // Adding to a non-existent category should return false
        assert!(!categories::add_domain_to_category(conn, "nonexistent", "foo.com")?);

        // List domains
        let doms = categories::list_category_domains(conn, "gaming")?;
        assert_eq!(doms.len(), 2);
        assert!(doms.contains(&"steam.com".to_string()));
        assert!(doms.contains(&"epic.com".to_string()));

        // Remove one domain
        let removed = categories::remove_domain_from_category(conn, "gaming", "steam.com")?;
        assert!(removed);

        let doms = categories::list_category_domains(conn, "gaming")?;
        assert_eq!(doms.len(), 1);
        assert_eq!(doms[0], "epic.com");

        // Remove non-existent domain returns false
        let removed = categories::remove_domain_from_category(conn, "gaming", "nonexistent.com")?;
        assert!(!removed);

        Ok(())
    })
    .expect("category domains test failed");
}

// ---------------------------------------------------------------------------
// 7. Pending action CRUD
// ---------------------------------------------------------------------------
#[test]
fn test_pending_action_crud() {
    let db = setup_db();

    db.with_conn(|conn| {
        let now = now_unix();
        let execute_at = now + 3600;

        // Create
        pending::create_pending(
            conn,
            "pa-001",
            "add",
            Some("bad.com"),
            "denylist",
            execute_at,
            Some("block bad site"),
        )?;

        // List all
        let all = pending::list_pending(conn, None)?;
        assert_eq!(all.len(), 1);
        assert_eq!(all[0].id, "pa-001");
        assert_eq!(all[0].status, "pending");

        // Get by id
        let pa = pending::get_pending(conn, "pa-001")?;
        assert!(pa.is_some());
        let pa = pa.unwrap();
        assert_eq!(pa.action, "add");
        assert_eq!(pa.domain.as_deref(), Some("bad.com"));
        assert_eq!(pa.list_type, "denylist");
        assert_eq!(pa.execute_at, execute_at);
        assert_eq!(pa.description.as_deref(), Some("block bad site"));

        // Get non-existent
        assert!(pending::get_pending(conn, "pa-999")?.is_none());

        // List by status
        let pending_list = pending::list_pending(conn, Some("pending"))?;
        assert_eq!(pending_list.len(), 1);

        // Update status
        let updated = pending::update_pending_status(conn, "pa-001", "completed")?;
        assert!(updated);

        let pa = pending::get_pending(conn, "pa-001")?.unwrap();
        assert_eq!(pa.status, "completed");

        // Filter by original status should now be empty
        let pending_list = pending::list_pending(conn, Some("pending"))?;
        assert!(pending_list.is_empty());

        // Cancel another action
        pending::create_pending(conn, "pa-002", "remove", None, "allowlist", execute_at, None)?;
        let cancelled = pending::cancel_pending(conn, "pa-002")?;
        assert!(cancelled);

        let pa2 = pending::get_pending(conn, "pa-002")?.unwrap();
        assert_eq!(pa2.status, "cancelled");

        Ok(())
    })
    .expect("pending action CRUD failed");
}

// ---------------------------------------------------------------------------
// 8. Audit log
// ---------------------------------------------------------------------------
#[test]
fn test_audit_log() {
    let db = setup_db();

    db.with_conn(|conn| {
        let no_filter = audit::AuditFilter { domain: None, action: None, source: None };

        // Initially empty
        assert_eq!(audit::count_audit(conn, &no_filter)?, 0);
        assert!(audit::list_audit(conn, 10, 0, &no_filter)?.is_empty());

        // Log an action
        let id = audit::log_action(conn, "block", "domain", "example.com", Some("blocked by user"), "cli")?;
        assert!(id > 0);

        // Count
        assert_eq!(audit::count_audit(conn, &no_filter)?, 1);

        // List
        let entries = audit::list_audit(conn, 10, 0, &no_filter)?;
        assert_eq!(entries.len(), 1);
        assert_eq!(entries[0].action, "block");
        assert_eq!(entries[0].target_type, "domain");
        assert_eq!(entries[0].target_id, "example.com");
        assert_eq!(entries[0].details.as_deref(), Some("blocked by user"));
        assert_eq!(entries[0].source, "cli");
        assert!(entries[0].timestamp > 0);

        // Log multiple with different sources and verify ordering (DESC by timestamp)
        audit::log_action(conn, "allow", "domain", "safe.com", None, "cli")?;
        audit::log_action(conn, "schedule_block", "domain", "social.com", Some("Schedule activated"), "schedule")?;

        assert_eq!(audit::count_audit(conn, &no_filter)?, 3);

        let entries = audit::list_audit(conn, 10, 0, &no_filter)?;
        assert_eq!(entries.len(), 3);

        // Verify limit and offset
        let page = audit::list_audit(conn, 1, 0, &no_filter)?;
        assert_eq!(page.len(), 1);

        let page2 = audit::list_audit(conn, 1, 1, &no_filter)?;
        assert_eq!(page2.len(), 1);
        assert_ne!(page[0].id, page2[0].id);

        // Verify source filter
        let schedule_filter = audit::AuditFilter { domain: None, action: None, source: Some("schedule".to_string()) };
        let schedule_entries = audit::list_audit(conn, 10, 0, &schedule_filter)?;
        assert_eq!(schedule_entries.len(), 1);
        assert_eq!(schedule_entries[0].source, "schedule");
        assert_eq!(audit::count_audit(conn, &schedule_filter)?, 1);

        // Verify domain filter
        let domain_filter = audit::AuditFilter { domain: Some("example.com".to_string()), action: None, source: None };
        let domain_entries = audit::list_audit(conn, 10, 0, &domain_filter)?;
        assert_eq!(domain_entries.len(), 1);
        assert_eq!(domain_entries[0].target_id, "example.com");

        // Verify action filter
        let action_filter = audit::AuditFilter { domain: None, action: Some("block".to_string()), source: None };
        let action_entries = audit::list_audit(conn, 10, 0, &action_filter)?;
        assert_eq!(action_entries.len(), 1);
        assert_eq!(action_entries[0].action, "block");

        Ok(())
    })
    .expect("audit log test failed");
}

// ---------------------------------------------------------------------------
// 10. NextDNS categories
// ---------------------------------------------------------------------------
#[test]
fn test_nextdns_categories() {
    let db = setup_db();

    db.with_conn(|conn| {
        // Initially empty
        assert!(nextdns::list_nextdns_categories(conn)?.is_empty());

        // Add
        nextdns::add_nextdns_category(conn, "gambling")?;
        nextdns::add_nextdns_category(conn, "malware")?;

        let list = nextdns::list_nextdns_categories(conn)?;
        assert_eq!(list.len(), 2);

        let ids: Vec<&str> = list.iter().map(|c| c.id.as_str()).collect();
        assert!(ids.contains(&"gambling"));
        assert!(ids.contains(&"malware"));
        assert!(list.iter().all(|c| c.active));

        // Duplicate insert (INSERT OR IGNORE) should not fail or create duplicates
        nextdns::add_nextdns_category(conn, "gambling")?;
        assert_eq!(nextdns::list_nextdns_categories(conn)?.len(), 2);

        // Remove
        let removed = nextdns::remove_nextdns_category(conn, "gambling")?;
        assert!(removed);

        let list = nextdns::list_nextdns_categories(conn)?;
        assert_eq!(list.len(), 1);
        assert_eq!(list[0].id, "malware");

        // Remove non-existent
        let removed = nextdns::remove_nextdns_category(conn, "nonexistent")?;
        assert!(!removed);

        Ok(())
    })
    .expect("nextdns categories test failed");
}

// ---------------------------------------------------------------------------
// 11. NextDNS services
// ---------------------------------------------------------------------------
#[test]
fn test_nextdns_services() {
    let db = setup_db();

    db.with_conn(|conn| {
        // Initially empty
        assert!(nextdns::list_nextdns_services(conn)?.is_empty());

        // Add
        nextdns::add_nextdns_service(conn, "tiktok")?;
        nextdns::add_nextdns_service(conn, "facebook")?;

        let list = nextdns::list_nextdns_services(conn)?;
        assert_eq!(list.len(), 2);

        let ids: Vec<&str> = list.iter().map(|s| s.id.as_str()).collect();
        assert!(ids.contains(&"tiktok"));
        assert!(ids.contains(&"facebook"));
        assert!(list.iter().all(|s| s.active));

        // Duplicate insert should not create duplicates
        nextdns::add_nextdns_service(conn, "tiktok")?;
        assert_eq!(nextdns::list_nextdns_services(conn)?.len(), 2);

        // Remove
        let removed = nextdns::remove_nextdns_service(conn, "tiktok")?;
        assert!(removed);

        let list = nextdns::list_nextdns_services(conn)?;
        assert_eq!(list.len(), 1);
        assert_eq!(list[0].id, "facebook");

        // Remove non-existent
        let removed = nextdns::remove_nextdns_service(conn, "nonexistent")?;
        assert!(!removed);

        Ok(())
    })
    .expect("nextdns services test failed");
}

// ---------------------------------------------------------------------------
// 12. App mappings CRUD
// ---------------------------------------------------------------------------
#[test]
fn test_app_mapping_crud() {
    let db = setup_db();

    db.with_conn(|conn| {
        // Initially empty
        assert!(apps::list_mappings(conn)?.is_empty());

        // Add mapping
        apps::add_mapping(conn, "whatsapp.com", "net.whatsapp.WhatsApp", "WhatsApp", false)?;
        apps::add_mapping(conn, "discord.com", "com.hnc.Discord", "Discord", true)?;

        let list = apps::list_mappings(conn)?;
        assert_eq!(list.len(), 2);

        // Get by domain
        let wa = apps::get_mappings_for_domain(conn, "whatsapp.com")?;
        assert_eq!(wa.len(), 1);
        assert_eq!(wa[0].bundle_id, "net.whatsapp.WhatsApp");
        assert_eq!(wa[0].app_name, "WhatsApp");
        assert!(!wa[0].auto);

        // Get by bundle
        let dc = apps::get_mappings_for_bundle(conn, "com.hnc.Discord")?;
        assert_eq!(dc.len(), 1);
        assert_eq!(dc[0].domain, "discord.com");
        assert!(dc[0].auto);

        // Upsert (update app_name)
        apps::add_mapping(conn, "whatsapp.com", "net.whatsapp.WhatsApp", "WhatsApp Desktop", true)?;
        let wa = apps::get_mappings_for_domain(conn, "whatsapp.com")?;
        assert_eq!(wa[0].app_name, "WhatsApp Desktop");
        assert!(wa[0].auto);

        // Remove
        let removed = apps::remove_mapping(conn, "discord.com", "com.hnc.Discord")?;
        assert!(removed);
        assert_eq!(apps::list_mappings(conn)?.len(), 1);

        // Remove non-existent
        let removed = apps::remove_mapping(conn, "discord.com", "com.hnc.Discord")?;
        assert!(!removed);

        Ok(())
    })
    .expect("app mapping CRUD failed");
}

// ---------------------------------------------------------------------------
// 13. Blocked apps CRUD
// ---------------------------------------------------------------------------
#[test]
fn test_blocked_app_crud() {
    let db = setup_db();

    db.with_conn(|conn| {
        // Initially empty
        assert!(apps::list_blocked_apps(conn)?.is_empty());

        // Add mapping (required for domain-based lookup via JOIN)
        apps::add_mapping(conn, "whatsapp.com", "net.whatsapp.WhatsApp", "WhatsApp", false)?;

        // Add blocked app
        apps::add_blocked_app(
            conn,
            "net.whatsapp.WhatsApp",
            "WhatsApp",
            "/Applications/WhatsApp.app",
            "/Applications/WhatsApp.app.blocked",
            Some("whatsapp.com"),
        )?;

        let list = apps::list_blocked_apps(conn)?;
        assert_eq!(list.len(), 1);
        assert_eq!(list[0].bundle_id, "net.whatsapp.WhatsApp");
        assert_eq!(list[0].app_name, "WhatsApp");
        assert_eq!(list[0].original_path, "/Applications/WhatsApp.app");
        assert_eq!(list[0].blocked_path, "/Applications/WhatsApp.app.blocked");
        assert_eq!(list[0].source_domain.as_deref(), Some("whatsapp.com"));

        // Get by bundle
        let app = apps::get_blocked_app(conn, "net.whatsapp.WhatsApp")?;
        assert!(app.is_some());

        // Get by domain (now uses JOIN with app_mappings)
        let by_domain = apps::get_blocked_apps_for_domain(conn, "whatsapp.com")?;
        assert_eq!(by_domain.len(), 1);

        // Get non-existent domain
        let empty = apps::get_blocked_apps_for_domain(conn, "other.com")?;
        assert!(empty.is_empty());

        // Verify multi-domain mapping: web.whatsapp.com should also find the blocked app
        apps::add_mapping(conn, "web.whatsapp.com", "net.whatsapp.WhatsApp", "WhatsApp", false)?;
        let by_alt_domain = apps::get_blocked_apps_for_domain(conn, "web.whatsapp.com")?;
        assert_eq!(by_alt_domain.len(), 1);
        assert_eq!(by_alt_domain[0].bundle_id, "net.whatsapp.WhatsApp");

        // Remove
        let removed = apps::remove_blocked_app(conn, "net.whatsapp.WhatsApp")?;
        assert!(removed);
        assert!(apps::list_blocked_apps(conn)?.is_empty());

        // Remove non-existent
        let removed = apps::remove_blocked_app(conn, "net.whatsapp.WhatsApp")?;
        assert!(!removed);

        Ok(())
    })
    .expect("blocked app CRUD failed");
}

// ---------------------------------------------------------------------------
// 14. Android package mapping CRUD
// ---------------------------------------------------------------------------
#[test]
fn test_android_mapping_crud() {
    let db = setup_db();

    db.with_conn(|conn| {
        // Initially empty
        assert!(android::list_mappings(conn)?.is_empty());

        // Add mappings
        android::add_mapping(conn, "youtube.com", "com.google.android.youtube", "YouTube", false)?;
        android::add_mapping(conn, "tiktok.com", "com.zhiliaoapp.musically", "TikTok", true)?;

        let list = android::list_mappings(conn)?;
        assert_eq!(list.len(), 2);

        // Get by domain
        let yt = android::get_mappings_for_domain(conn, "youtube.com")?;
        assert_eq!(yt.len(), 1);
        assert_eq!(yt[0].package_name, "com.google.android.youtube");
        assert_eq!(yt[0].display_name, "YouTube");
        assert!(!yt[0].auto);

        // Upsert (update display_name)
        android::add_mapping(conn, "youtube.com", "com.google.android.youtube", "YouTube App", true)?;
        let yt = android::get_mappings_for_domain(conn, "youtube.com")?;
        assert_eq!(yt[0].display_name, "YouTube App");
        assert!(yt[0].auto);

        // Non-existent domain
        let empty = android::get_mappings_for_domain(conn, "nonexistent.com")?;
        assert!(empty.is_empty());

        Ok(())
    })
    .expect("android mapping CRUD failed");
}

// ---------------------------------------------------------------------------
// 15. Remote Android blocked CRUD
// ---------------------------------------------------------------------------
#[test]
fn test_remote_android_blocked_crud() {
    let db = setup_db();

    db.with_conn(|conn| {
        // Initially empty
        assert!(android::list_remote_blocked(conn)?.is_empty());

        // Add blocked package
        android::add_remote_blocked(conn, "com.google.android.youtube", "youtube.com", "android_pixel", None)?;
        android::add_remote_blocked(conn, "com.zhiliaoapp.musically", "tiktok.com", "android_pixel", Some(1710003600))?;

        let list = android::list_remote_blocked(conn)?;
        assert_eq!(list.len(), 2);

        // Check fields
        let yt = list.iter().find(|e| e.package_name == "com.google.android.youtube").unwrap();
        assert_eq!(yt.domain, "youtube.com");
        assert_eq!(yt.device_id, "android_pixel");
        assert!(yt.unblock_at.is_none());
        assert!(!yt.in_firebase);

        let tt = list.iter().find(|e| e.package_name == "com.zhiliaoapp.musically").unwrap();
        assert_eq!(tt.unblock_at, Some(1710003600));

        // Get by domain
        let by_domain = android::get_blocked_for_domain(conn, "youtube.com")?;
        assert_eq!(by_domain.len(), 1);
        assert_eq!(by_domain[0].package_name, "com.google.android.youtube");

        // Set in_firebase
        android::set_in_firebase(conn, "com.google.android.youtube", true, None)?;
        let pending = android::get_pending_push(conn)?;
        assert_eq!(pending.len(), 1); // only tiktok still pending
        assert_eq!(pending[0].package_name, "com.zhiliaoapp.musically");

        // Set error
        android::set_in_firebase(conn, "com.zhiliaoapp.musically", false, Some("network error"))?;
        let pending = android::get_pending_push(conn)?;
        assert_eq!(pending.len(), 1);
        assert_eq!(pending[0].push_error.as_deref(), Some("network error"));

        // Remove
        let removed = android::remove_remote_blocked(conn, "com.google.android.youtube")?;
        assert!(removed);
        assert_eq!(android::list_remote_blocked(conn)?.len(), 1);

        // Remove non-existent
        let removed = android::remove_remote_blocked(conn, "com.google.android.youtube")?;
        assert!(!removed);

        Ok(())
    })
    .expect("remote android blocked CRUD failed");
}

// ---------------------------------------------------------------------------
// 16. Blocked domain deactivate / activate
// ---------------------------------------------------------------------------
#[test]
fn test_blocked_domain_deactivate_activate() {
    let db = setup_db();

    db.with_conn(|conn| {
        // Add a domain (active by default)
        domains::add_blocked(conn, "toggle.com", Some("toggle test"), None, None)?;
        assert!(domains::is_blocked(conn, "toggle.com")?);
        assert_eq!(domains::count_blocked(conn)?, 1);

        // Deactivate
        let deactivated = domains::deactivate_blocked(conn, "toggle.com")?;
        assert!(deactivated);

        // is_blocked should return false (checks active = 1)
        assert!(!domains::is_blocked(conn, "toggle.com")?);

        // count_blocked only counts active
        assert_eq!(domains::count_blocked(conn)?, 0);

        // The domain should still exist in the full list
        let all = domains::list_blocked(conn, false)?;
        assert_eq!(all.len(), 1);
        assert!(!all[0].active);

        // Active-only list should be empty
        let active = domains::list_blocked(conn, true)?;
        assert!(active.is_empty());

        // Deactivating again should return false (already inactive)
        let deactivated = domains::deactivate_blocked(conn, "toggle.com")?;
        assert!(!deactivated);

        Ok(())
    })
    .expect("blocked domain deactivate/activate failed");
}
