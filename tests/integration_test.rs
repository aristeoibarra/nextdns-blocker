use nextdns_blocker::common::time::now_unix;
use nextdns_blocker::db::Database;

fn setup_db() -> Database {
    Database::open_memory().expect("failed to open in-memory database")
}

// ---------------------------------------------------------------------------
// 1. Block + audit trail
// ---------------------------------------------------------------------------
#[test]
fn block_creates_domain_and_audit_entry() {
    let db = setup_db();

    db.with_transaction(|conn| {
        nextdns_blocker::db::domains::add_blocked(conn, "bad.com", Some("test"), None, None)?;
        nextdns_blocker::db::audit::log_action(conn, "block", "domain", "bad.com", None)?;
        Ok(())
    })
    .expect("transaction failed");

    let is_blocked = db
        .with_conn(|conn| nextdns_blocker::db::domains::is_blocked(conn, "bad.com"))
        .unwrap();
    assert!(is_blocked);

    let audit = db
        .with_conn(|conn| nextdns_blocker::db::audit::list_audit(conn, 10, 0))
        .unwrap();
    assert_eq!(audit.len(), 1);
    assert_eq!(audit[0].action, "block");
    assert_eq!(audit[0].target_id, "bad.com");
}

// ---------------------------------------------------------------------------
// 2. Unblock removes domain + creates audit
// ---------------------------------------------------------------------------
#[test]
fn unblock_removes_domain_and_audits() {
    let db = setup_db();

    db.with_conn(|conn| {
        nextdns_blocker::db::domains::add_blocked(conn, "remove-me.com", None, None, None)
    })
    .unwrap();

    let removed = db
        .with_conn(|conn| nextdns_blocker::db::domains::remove_blocked(conn, "remove-me.com"))
        .unwrap();
    assert!(removed);

    db.with_conn(|conn| {
        nextdns_blocker::db::audit::log_action(conn, "unblock", "domain", "remove-me.com", None)
    })
    .unwrap();

    assert!(!db
        .with_conn(|conn| nextdns_blocker::db::domains::is_blocked(conn, "remove-me.com"))
        .unwrap());

    let audit = db
        .with_conn(|conn| nextdns_blocker::db::audit::list_audit(conn, 10, 0))
        .unwrap();
    assert_eq!(audit[0].action, "unblock");
}

// ---------------------------------------------------------------------------
// 3. Temporary block with pending re-add
// ---------------------------------------------------------------------------
#[test]
fn temporary_unblock_creates_pending_reblock() {
    let db = setup_db();

    db.with_conn(|conn| {
        nextdns_blocker::db::domains::add_blocked(conn, "temp.com", None, None, None)
    })
    .unwrap();

    // Deactivate (temporary unblock)
    db.with_conn(|conn| nextdns_blocker::db::domains::deactivate_blocked(conn, "temp.com"))
        .unwrap();

    // Create pending re-block
    let execute_at = now_unix() + 3600;
    db.with_conn(|conn| {
        nextdns_blocker::db::pending::create_pending(
            conn,
            "pa-temp-001",
            "add",
            Some("temp.com"),
            "denylist",
            execute_at,
            Some("Auto re-block after 1h"),
        )
    })
    .unwrap();

    // Domain should be inactive
    assert!(!db
        .with_conn(|conn| nextdns_blocker::db::domains::is_blocked(conn, "temp.com"))
        .unwrap());

    // Pending action exists
    let pa = db
        .with_conn(|conn| nextdns_blocker::db::pending::get_pending(conn, "pa-temp-001"))
        .unwrap()
        .unwrap();
    assert_eq!(pa.action, "add");
    assert_eq!(pa.domain.as_deref(), Some("temp.com"));
}

// ---------------------------------------------------------------------------
// 4. Transaction rollback on error
// ---------------------------------------------------------------------------
#[test]
fn transaction_rolls_back_on_error() {
    let db = setup_db();

    let result: Result<(), _> = db.with_transaction(|conn| {
        nextdns_blocker::db::domains::add_blocked(conn, "rollback.com", None, None, None)?;
        // Force an error
        Err(nextdns_blocker::error::AppError::General {
            message: "forced error".to_string(),
            hint: None,
        })
    });
    assert!(result.is_err());

    // Domain should NOT exist due to rollback
    assert!(!db
        .with_conn(|conn| nextdns_blocker::db::domains::is_blocked(conn, "rollback.com"))
        .unwrap());
}

// ---------------------------------------------------------------------------
// 5. Multi-domain block in transaction is atomic
// ---------------------------------------------------------------------------
#[test]
fn multi_domain_block_atomic() {
    let db = setup_db();

    db.with_transaction(|conn| {
        for domain in &["a.com", "b.com", "c.com"] {
            nextdns_blocker::db::domains::add_blocked(conn, domain, Some("batch"), None, None)?;
            nextdns_blocker::db::audit::log_action(conn, "block", "domain", domain, None)?;
        }
        Ok(())
    })
    .unwrap();

    assert_eq!(
        db.with_conn(nextdns_blocker::db::domains::count_blocked).unwrap(),
        3
    );
    assert_eq!(
        db.with_conn(nextdns_blocker::db::audit::count_audit).unwrap(),
        3
    );
}

// ---------------------------------------------------------------------------
// 6. Category + domains + block flow
// ---------------------------------------------------------------------------
#[test]
fn category_with_domains_flow() {
    let db = setup_db();

    db.with_transaction(|conn| {
        nextdns_blocker::db::categories::create_category(conn, "gaming", Some("Game sites"), None)?;
        nextdns_blocker::db::categories::add_domain_to_category(conn, "gaming", "steam.com")?;
        nextdns_blocker::db::categories::add_domain_to_category(conn, "gaming", "epic.com")?;

        // Block all domains in the category
        let domains = nextdns_blocker::db::categories::list_category_domains(conn, "gaming")?;
        for domain in &domains {
            nextdns_blocker::db::domains::add_blocked(conn, domain, None, Some("gaming"), None)?;
        }
        Ok(())
    })
    .unwrap();

    assert_eq!(
        db.with_conn(nextdns_blocker::db::domains::count_blocked).unwrap(),
        2
    );

    let list = db
        .with_conn(|conn| nextdns_blocker::db::domains::list_blocked(conn, true))
        .unwrap();
    assert!(list.iter().all(|d| d.category.as_deref() == Some("gaming")));
}

// ---------------------------------------------------------------------------
// 7. Pending action lifecycle
// ---------------------------------------------------------------------------
#[test]
fn pending_action_full_lifecycle() {
    let db = setup_db();
    let now = now_unix();

    // Create pending
    db.with_conn(|conn| {
        nextdns_blocker::db::pending::create_pending(
            conn,
            "pa-lifecycle",
            "remove",
            Some("expire.com"),
            "denylist",
            now - 10, // already due
            Some("auto-expire"),
        )
    })
    .unwrap();

    // Get due pending actions
    let due = db
        .with_conn(nextdns_blocker::db::pending::get_due_pending)
        .unwrap();
    assert_eq!(due.len(), 1);
    assert_eq!(due[0].id, "pa-lifecycle");

    // Execute: mark as completed
    db.with_conn(|conn| {
        nextdns_blocker::db::pending::update_pending_status(conn, "pa-lifecycle", "completed")
    })
    .unwrap();

    // Should no longer be due
    let due = db
        .with_conn(nextdns_blocker::db::pending::get_due_pending)
        .unwrap();
    assert!(due.is_empty());
}

// ---------------------------------------------------------------------------
// 8. Retry queue lifecycle
// ---------------------------------------------------------------------------
#[test]
fn retry_queue_lifecycle() {
    let db = setup_db();
    let now = now_unix();

    // Enqueue a retry
    db.with_conn(|conn| {
        nextdns_blocker::db::retry::enqueue_retry(
            conn,
            "retry-001",
            "add",
            Some("retry.com"),
            "denylist",
            None,
            3,
            now - 10,
        )
    })
    .unwrap();

    // Should be due
    let due = db
        .with_conn(nextdns_blocker::db::retry::get_due_retries)
        .unwrap();
    assert_eq!(due.len(), 1);

    // Increment attempt (simulating failure)
    let next_retry = now + 60;
    db.with_conn(|conn| {
        nextdns_blocker::db::retry::increment_retry(conn, "retry-001", "timeout", next_retry)
    })
    .unwrap();

    // Should not be due anymore (next_retry is in the future)
    let due = db
        .with_conn(nextdns_blocker::db::retry::get_due_retries)
        .unwrap();
    assert!(due.is_empty());

    // Remove after success
    db.with_conn(|conn| nextdns_blocker::db::retry::remove_retry(conn, "retry-001"))
        .unwrap();

    assert_eq!(
        db.with_conn(nextdns_blocker::db::retry::count_retries).unwrap(),
        0
    );
}

// ---------------------------------------------------------------------------
// 9. NextDNS categories + services stored correctly
// ---------------------------------------------------------------------------
#[test]
fn nextdns_categories_and_services_stored() {
    let db = setup_db();

    db.with_transaction(|conn| {
        nextdns_blocker::db::nextdns::add_nextdns_category(conn, "gambling")?;
        nextdns_blocker::db::nextdns::add_nextdns_category(conn, "malware")?;
        nextdns_blocker::db::nextdns::add_nextdns_service(conn, "tiktok")?;
        nextdns_blocker::db::nextdns::add_nextdns_service(conn, "facebook")?;
        Ok(())
    })
    .unwrap();

    let cats = db
        .with_conn(nextdns_blocker::db::nextdns::list_nextdns_categories)
        .unwrap();
    assert_eq!(cats.len(), 2);

    let svcs = db
        .with_conn(nextdns_blocker::db::nextdns::list_nextdns_services)
        .unwrap();
    assert_eq!(svcs.len(), 2);
}

// ---------------------------------------------------------------------------
// 10. Config kv operations
// ---------------------------------------------------------------------------
#[test]
fn config_kv_operations() {
    let db = setup_db();

    // Default timezone should exist after migration
    let tz = db
        .with_conn(nextdns_blocker::db::config::get_timezone)
        .unwrap();
    assert!(!tz.is_empty());

    // Set and get custom value
    db.with_conn(|conn| {
        nextdns_blocker::db::config::set_value(conn, "timezone", "America/Mexico_City")
    })
    .unwrap();

    let val = db
        .with_conn(|conn| nextdns_blocker::db::config::get_value(conn, "timezone"))
        .unwrap();
    assert_eq!(val.as_deref(), Some("America/Mexico_City"));

    // List all
    let all = db.with_conn(nextdns_blocker::db::config::list_all).unwrap();
    assert!(!all.is_empty());
}
