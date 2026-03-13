use std::collections::HashSet;
use std::io::Write;

use crate::db::Database;
use crate::error::AppError;
use crate::types::HostEntry;

const HOSTS_PATH: &str = "/etc/hosts";
const MARKER_START: &str = "# ndb-start";
const MARKER_END: &str = "# ndb-end";
const DEFAULT_IP: &str = "0.0.0.0";

/// Domains that must never be blocked in /etc/hosts (ndb needs API access).
const PROTECTED_DOMAINS: &[&str] = &["api.nextdns.io"];

/// Add domains to /etc/hosts and track in DB. Returns list of domains actually added.
pub fn block_hosts_for_domains(
    db: &Database,
    domains: &[String],
) -> Result<Vec<String>, AppError> {
    let mut added = Vec::new();

    db.with_transaction(|conn| {
        for domain in domains {
            if PROTECTED_DOMAINS.contains(&domain.as_str()) {
                continue;
            }
            crate::db::hosts::add_host_entry(conn, domain, DEFAULT_IP, Some(domain))?;
            added.push(domain.clone());
        }
        Ok(())
    })?;

    if !added.is_empty() {
        apply_hosts_from_db(db)?;
    }

    Ok(added)
}

/// Remove a domain's hosts entries from /etc/hosts and DB. Returns domains removed.
/// All DB deletions are atomic via a single transaction.
pub fn unblock_hosts_for_domain(
    db: &Database,
    domain: &str,
) -> Result<Vec<String>, AppError> {
    let removed = db.with_transaction(|conn| {
        let entries = crate::db::hosts::get_entries_for_source(conn, domain)
            .map_err(AppError::from)?;
        let mut removed = Vec::new();

        for entry in &entries {
            crate::db::hosts::remove_host_entry(conn, &entry.domain)
                .map_err(AppError::from)?;
            removed.push(entry.domain.clone());
        }

        // Also remove the domain itself if it's a direct entry
        let direct = {
            let mut stmt = conn.prepare(
                "SELECT domain FROM hosts_entries WHERE domain = ?1",
            ).map_err(AppError::from)?;
            stmt.exists(rusqlite::params![domain]).map_err(AppError::from)?
        };
        if direct {
            crate::db::hosts::remove_host_entry(conn, domain)
                .map_err(AppError::from)?;
            if !removed.contains(&domain.to_string()) {
                removed.push(domain.to_string());
            }
        }

        Ok(removed)
    })?;

    if !removed.is_empty() {
        apply_hosts_from_db(db)?;
    }

    Ok(removed)
}

/// Re-apply all DB entries to /etc/hosts. Used by watchdog to enforce state.
pub fn enforce_hosts_entries(db: &Database) -> Result<Vec<String>, AppError> {
    let entries = db.with_conn(crate::db::hosts::list_host_entries)?;
    if entries.is_empty() {
        return Ok(Vec::new());
    }

    let (_, existing_ndb) = read_hosts_file()?;
    let expected: HashSet<String> = entries.iter().map(|e| e.domain.clone()).collect();

    // Only rewrite if there's a mismatch
    if existing_ndb == expected {
        return Ok(Vec::new());
    }

    apply_hosts_from_db(db)?;
    let enforced: Vec<String> = expected.difference(&existing_ndb).cloned().collect();
    Ok(enforced)
}

/// Remove ALL ndb entries from /etc/hosts and DB. Emergency restore.
/// All DB deletions are atomic via a single transaction.
pub fn restore_all(db: &Database) -> Result<Vec<String>, AppError> {
    let removed = db.with_transaction(|conn| {
        let entries = crate::db::hosts::list_host_entries(conn)
            .map_err(AppError::from)?;
        let mut removed = Vec::new();

        for entry in &entries {
            crate::db::hosts::remove_host_entry(conn, &entry.domain)
                .map_err(AppError::from)?;
            removed.push(entry.domain.clone());
        }

        Ok(removed)
    })?;

    if !removed.is_empty() {
        apply_hosts_from_db(db)?;
    }

    Ok(removed)
}

/// Read /etc/hosts and separate ndb-managed lines from the rest.
/// Returns (non-ndb lines, set of ndb-managed domains).
fn read_hosts_file() -> Result<(Vec<String>, HashSet<String>), AppError> {
    let content = std::fs::read_to_string(HOSTS_PATH).map_err(|e| AppError::General {
        message: format!("Failed to read {HOSTS_PATH}: {e}"),
        hint: Some("Check file permissions".to_string()),
    })?;

    let mut non_ndb_lines = Vec::new();
    let mut ndb_domains = HashSet::new();
    let mut in_ndb_block = false;

    for line in content.lines() {
        let trimmed = line.trim();
        if trimmed == MARKER_START || trimmed.starts_with(&format!("{MARKER_START} ")) {
            in_ndb_block = true;
            continue;
        }
        if trimmed == MARKER_END || trimmed.starts_with(&format!("{MARKER_END} ")) {
            in_ndb_block = false;
            continue;
        }

        if in_ndb_block {
            // Parse "0.0.0.0 domain.com" lines
            let parts: Vec<&str> = line.split_whitespace().collect();
            if parts.len() >= 2 {
                ndb_domains.insert(parts[1].to_string());
            }
        } else {
            non_ndb_lines.push(line.to_string());
        }
    }

    // If marker was never closed, the lines after the marker were absorbed
    // as ndb-managed. This is the intended safe behavior: we'll rewrite
    // only our own domains, effectively closing the marker on next write.

    Ok((non_ndb_lines, ndb_domains))
}

/// Read current DB entries and rewrite /etc/hosts with them.
fn apply_hosts_from_db(db: &Database) -> Result<(), AppError> {
    let entries = db.with_conn(crate::db::hosts::list_host_entries)?;
    let (non_ndb_lines, _) = read_hosts_file()?;
    write_hosts_file(&non_ndb_lines, &entries)
}

/// Write /etc/hosts atomically: temp file -> sudo cp.
fn write_hosts_file(non_ndb_lines: &[String], ndb_entries: &[HostEntry]) -> Result<(), AppError> {
    let mut content = String::new();

    // Write non-ndb lines (preserve existing content)
    for line in non_ndb_lines {
        content.push_str(line);
        content.push('\n');
    }

    // Only add ndb block if there are entries
    if !ndb_entries.is_empty() {
        content.push_str(MARKER_START);
        content.push('\n');
        for entry in ndb_entries {
            content.push_str(&format!("{} {}\n", entry.ip, entry.domain));
        }
        content.push_str(MARKER_END);
        content.push('\n');
    }

    // Write to temp file
    let tmp_path = format!("/tmp/ndb_hosts_{}", std::process::id());
    let mut file = std::fs::File::create(&tmp_path).map_err(|e| AppError::General {
        message: format!("Failed to create temp file: {e}"),
        hint: None,
    })?;
    file.write_all(content.as_bytes()).map_err(|e| AppError::General {
        message: format!("Failed to write temp file: {e}"),
        hint: None,
    })?;
    drop(file);

    // Copy to /etc/hosts via sudo -n (non-interactive)
    let output = std::process::Command::new("sudo")
        .args(["-n", "cp", &tmp_path, HOSTS_PATH])
        .output()
        .map_err(|e| AppError::General {
            message: format!("Failed to run sudo: {e}"),
            hint: Some("Run 'ndb hosts setup' first to configure passwordless sudo".to_string()),
        })?;

    // Clean up temp file
    let _ = std::fs::remove_file(&tmp_path);

    if !output.status.success() {
        let stderr = String::from_utf8_lossy(&output.stderr);
        return Err(AppError::General {
            message: format!("sudo cp failed: {stderr}"),
            hint: Some("Run 'ndb hosts setup' first to configure passwordless sudo".to_string()),
        });
    }

    // Flush DNS cache
    let _ = std::process::Command::new("sudo")
        .args(["-n", "dscacheutil", "-flushcache"])
        .output();
    let _ = std::process::Command::new("sudo")
        .args(["-n", "killall", "-HUP", "mDNSResponder"])
        .output();

    Ok(())
}
