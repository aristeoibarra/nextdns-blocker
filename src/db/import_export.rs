use rusqlite::Connection;

use crate::common::time::now_unix;

/// Export the full database state as JSON.
pub fn export_full(conn: &Connection) -> Result<serde_json::Value, rusqlite::Error> {
    let blocked = super::domains::list_blocked(conn, false)?;
    let allowed = super::domains::list_allowed(conn, false)?;
    let categories = super::categories::list_categories(conn)?;
    let nextdns_cats = super::nextdns::list_nextdns_categories(conn)?;
    let nextdns_svcs = super::nextdns::list_nextdns_services(conn)?;
    let kv = super::config::list_all(conn)?;

    // Build category domains map
    let mut cat_domains = serde_json::Map::new();
    for cat in &categories {
        let domains = super::categories::list_category_domains(conn, &cat.name)?;
        cat_domains.insert(
            cat.name.clone(),
            serde_json::Value::Array(domains.into_iter().map(serde_json::Value::String).collect()),
        );
    }

    Ok(serde_json::json!({
        "version": 1,
        "exported_at": now_unix(),
        "blocked_domains": blocked,
        "allowed_domains": allowed,
        "categories": categories,
        "category_domains": cat_domains,
        "nextdns_categories": nextdns_cats,
        "nextdns_services": nextdns_svcs,
        "kv_config": kv.into_iter().collect::<std::collections::HashMap<_, _>>(),
    }))
}
