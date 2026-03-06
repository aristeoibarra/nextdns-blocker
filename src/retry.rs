use crate::api::NextDnsClient;
use crate::config::constants::{RETRY_BASE_DELAY_SECS, RETRY_MAX_DELAY_SECS};
use crate::db::Database;
use crate::error::AppError;

/// Process all due retry entries.
pub async fn process_retries(db: &Database, client: &NextDnsClient) -> Result<RetryResult, AppError> {
    let entries = db.with_conn(|conn| crate::db::retry::get_due_retries(conn))?;

    let mut succeeded = 0;
    let mut failed = 0;
    let mut exhausted = 0;

    for entry in entries {
        let result = match (entry.action.as_str(), entry.list_type.as_str()) {
            ("add", "denylist") => {
                if let Some(ref domain) = entry.domain {
                    client.add_to_denylist(domain).await
                } else {
                    continue;
                }
            }
            ("remove", "denylist") => {
                if let Some(ref domain) = entry.domain {
                    client.remove_from_denylist(domain).await
                } else {
                    continue;
                }
            }
            ("add", "allowlist") => {
                if let Some(ref domain) = entry.domain {
                    client.add_to_allowlist(domain).await
                } else {
                    continue;
                }
            }
            ("remove", "allowlist") => {
                if let Some(ref domain) = entry.domain {
                    client.remove_from_allowlist(domain).await
                } else {
                    continue;
                }
            }
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
                    exhausted += 1;
                } else {
                    let delay = calculate_backoff(next_attempt as u32);
                    let next_retry = crate::common::time::now_unix() + delay as i64;
                    db.with_conn(|conn| {
                        crate::db::retry::increment_retry(conn, &entry.id, &e.to_string(), next_retry)
                    })?;
                    failed += 1;
                }
            }
        }
    }

    Ok(RetryResult {
        succeeded,
        failed,
        exhausted,
    })
}

/// Exponential backoff with full jitter.
fn calculate_backoff(attempt: u32) -> u64 {
    let base = RETRY_BASE_DELAY_SECS;
    let max = RETRY_MAX_DELAY_SECS;
    let exp_delay = base.saturating_mul(2u64.saturating_pow(attempt));
    let capped = exp_delay.min(max);
    rand::random::<u64>() % (capped + 1)
}

#[derive(Debug, serde::Serialize)]
pub struct RetryResult {
    pub succeeded: usize,
    pub failed: usize,
    pub exhausted: usize,
}
