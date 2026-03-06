use std::time::Duration;

use crate::error::AppError;

/// Parse a human-readable duration string like "30m", "2h", "1d", "1h30m".
///
/// Uses the `humantime` crate for parsing.
pub fn parse_duration(s: &str) -> Result<Duration, AppError> {
    humantime::parse_duration(s).map_err(|e| AppError::Validation {
        message: format!("Invalid duration '{s}': {e}"),
        details: vec![],
        hint: Some("Use formats like '30m', '2h', '1d', '1h30m'".to_string()),
    })
}

/// Format a duration as a human-readable string.
pub fn format_duration(d: Duration) -> String {
    humantime::format_duration(d).to_string()
}

/// Format a Unix timestamp as ISO 8601 UTC.
pub fn format_timestamp(ts: i64) -> String {
    chrono::DateTime::from_timestamp(ts, 0)
        .map(|dt| dt.to_rfc3339_opts(chrono::SecondsFormat::Secs, true))
        .unwrap_or_else(|| "invalid".to_string())
}

/// Get current Unix timestamp.
pub fn now_unix() -> i64 {
    chrono::Utc::now().timestamp()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parse_valid_durations() {
        assert_eq!(parse_duration("30m").unwrap(), Duration::from_secs(30 * 60));
        assert_eq!(parse_duration("2h").unwrap(), Duration::from_secs(2 * 3600));
        assert_eq!(
            parse_duration("1d").unwrap(),
            Duration::from_secs(24 * 3600)
        );
    }

    #[test]
    fn parse_invalid_duration() {
        assert!(parse_duration("abc").is_err());
        assert!(parse_duration("").is_err());
    }

    #[test]
    fn format_timestamp_works() {
        let s = format_timestamp(0);
        assert_eq!(s, "1970-01-01T00:00:00Z");
    }
}
