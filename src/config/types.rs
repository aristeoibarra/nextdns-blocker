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
    /// Load from environment variables.
    pub fn from_env() -> Result<Self, crate::error::AppError> {
        let api_key = std::env::var("NEXTDNS_API_KEY").map_err(|_| crate::error::AppError::Config {
            message: "Missing NEXTDNS_API_KEY environment variable".to_string(),
            hint: Some("Set NEXTDNS_API_KEY in your environment or .env file".to_string()),
        })?;

        let profile_id =
            std::env::var("NEXTDNS_PROFILE_ID").map_err(|_| crate::error::AppError::Config {
                message: "Missing NEXTDNS_PROFILE_ID environment variable".to_string(),
                hint: Some("Set NEXTDNS_PROFILE_ID in your environment or .env file".to_string()),
            })?;

        Ok(Self {
            api_key: secrecy::SecretString::from(api_key),
            profile_id,
        })
    }
}
