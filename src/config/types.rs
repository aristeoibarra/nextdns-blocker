use serde::{Deserialize, Serialize};

/// Schedule definition with available hours per day group.
/// Stored as JSON in database schedule columns.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Schedule {
    pub available_hours: Vec<AvailableHoursBlock>,
}

/// A block of days with their allowed time ranges.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AvailableHoursBlock {
    pub days: Vec<String>,
    pub time_ranges: Vec<TimeRange>,
}

/// A time range within a day.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TimeRange {
    pub start: String,
    pub end: String,
}

/// Environment-based secrets (not stored in DB).
#[derive(Debug, Clone)]
pub struct EnvConfig {
    pub api_key: secrecy::SecretString,
    pub profile_id: String,
}

impl EnvConfig {
    /// Load API credentials. Priority: env vars > macOS Keychain.
    pub fn from_env() -> Result<Self, crate::error::AppError> {
        let api_key = std::env::var("NEXTDNS_API_KEY").ok()
            .or_else(|| crate::common::keychain::get_secret("api-key").ok().flatten())
            .ok_or_else(|| crate::error::AppError::Config {
                message: "Missing NEXTDNS_API_KEY".to_string(),
                hint: Some("Set env var NEXTDNS_API_KEY or run 'ndb config set-secret api-key <value>'".to_string()),
            })?;

        let profile_id = std::env::var("NEXTDNS_PROFILE_ID").ok()
            .or_else(|| crate::common::keychain::get_secret("profile-id").ok().flatten())
            .ok_or_else(|| crate::error::AppError::Config {
                message: "Missing NEXTDNS_PROFILE_ID".to_string(),
                hint: Some("Set env var NEXTDNS_PROFILE_ID or run 'ndb config set-secret profile-id <value>'".to_string()),
            })?;

        Ok(Self {
            api_key: secrecy::SecretString::from(api_key),
            profile_id,
        })
    }
}
