use crate::api::NextDnsClient;
use crate::config::constants::{RETRY_BASE_DELAY_SECS, RETRY_MAX_DELAY_SECS};
use crate::db::Database;
use crate::error::AppError;

/// Process all due retry entries.
pub fn process_retries(db: &Database, client: &NextDnsClient) -> Result<RetryResult, AppError> {
    let entries = db.with_conn(crate::db::retry::get_due_retries)?;

    let mut succeeded = 0;
    let mut failed = 0;
    let mut exhausted = 0;

    for entry in entries {
        let domain = match entry.domain.as_deref() {
            Some(d) => d,
            None => continue,
        };

        let result = match (entry.action.as_str(), entry.list_type.as_str()) {
            ("add", "denylist") => client.add_to_denylist(domain),
            ("remove", "denylist") => client.remove_from_denylist(domain),
            ("add", "allowlist") => client.add_to_allowlist(domain),
            ("remove", "allowlist") => client.remove_from_allowlist(domain),
            _ => continue,
        };

        match result {
            Ok(()) => {
                db.with_conn(|conn| crate::db::retry::remove_retry(conn, &entry.id))?;
                succeeded += 1;
            }
            Err(e) => {
                let next_attempt = entry.attempts + 1;
                if next_attempt >= entry.max_attempts {
                    // Audit log before removing — don't lose trace
                    let details = format!(
                        "Exhausted after {} attempts. Last error: {}",
                        entry.max_attempts, e
                    );
                    let _ = db.with_conn(|conn| {
                        crate::db::audit::log_action(
                            conn, "retry_exhausted", "domain", domain, Some(&details),
                        )
                    });
                    let _ = db.with_conn(|conn| crate::db::retry::remove_retry(conn, &entry.id));
                    exhausted += 1;
                } else {
                    let delay = calculate_backoff(next_attempt as u32);
                    let next_retry = crate::common::time::now_unix() + delay as i64;
                    let err_msg = e.to_string();
                    db.with_conn(|conn| {
                        crate::db::retry::increment_retry(conn, &entry.id, &err_msg, next_retry)
                    })?;
                    failed += 1;
                }
            }
        }
    }

    Ok(RetryResult { succeeded, failed, exhausted })
}

/// Exponential backoff with full jitter (no external crate needed).
fn calculate_backoff(attempt: u32) -> u64 {
    let base = RETRY_BASE_DELAY_SECS;
    let max = RETRY_MAX_DELAY_SECS;
    let exp_delay = base.saturating_mul(2u64.saturating_pow(attempt));
    let capped = exp_delay.min(max);
    cheap_random_u64() % (capped + 1)
}

/// Quick non-crypto random u64 using std only (sufficient for jitter).
fn cheap_random_u64() -> u64 {
    use std::collections::hash_map::DefaultHasher;
    use std::hash::{Hash, Hasher};
    let mut h = DefaultHasher::new();
    std::time::SystemTime::now().hash(&mut h);
    std::thread::current().id().hash(&mut h);
    h.finish()
}

#[derive(Debug, serde::Serialize)]
pub struct RetryResult {
    pub succeeded: usize,
    pub failed: usize,
    pub exhausted: usize,
}
