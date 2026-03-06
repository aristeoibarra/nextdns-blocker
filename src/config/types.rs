use serde::{Deserialize, Serialize};

/// Top-level application configuration (config.json).
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AppConfig {
    #[serde(default = "default_version")]
    pub version: String,
    #[serde(default)]
    pub settings: Settings,
    #[serde(default)]
    pub nextdns: NextDnsConfig,
    #[serde(default)]
    pub categories: Vec<CategoryConfig>,
    #[serde(default)]
    pub blocklist: Vec<BlocklistEntry>,
    #[serde(default)]
    pub allowlist: Vec<AllowlistEntry>,
}

fn default_version() -> String {
    "1.0".to_string()
}

#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct Settings {
    pub editor: Option<String>,
    pub timezone: Option<String>,
}

#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct NextDnsConfig {
    #[serde(default)]
    pub parental_control: ParentalControl,
    #[serde(default)]
    pub categories: Vec<NextDnsCategoryConfig>,
    #[serde(default)]
    pub services: Vec<NextDnsServiceConfig>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ParentalControl {
    #[serde(default = "bool_true")]
    pub safe_search: bool,
    #[serde(default)]
    pub youtube_restricted_mode: bool,
    #[serde(default = "bool_true")]
    pub block_bypass: bool,
}

impl Default for ParentalControl {
    fn default() -> Self {
        Self {
            safe_search: true,
            youtube_restricted_mode: false,
            block_bypass: true,
        }
    }
}

fn bool_true() -> bool {
    true
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct NextDnsCategoryConfig {
    pub id: String,
    #[serde(default)]
    pub description: Option<String>,
    #[serde(default = "default_unblock_delay")]
    pub unblock_delay: String,
    pub schedule: Option<Schedule>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct NextDnsServiceConfig {
    pub id: String,
    #[serde(default)]
    pub description: Option<String>,
    #[serde(default = "default_unblock_delay")]
    pub unblock_delay: String,
    pub schedule: Option<Schedule>,
}

fn default_unblock_delay() -> String {
    "0".to_string()
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CategoryConfig {
    pub id: String,
    #[serde(default)]
    pub description: Option<String>,
    #[serde(default = "default_unblock_delay")]
    pub unblock_delay: String,
    pub schedule: Option<Schedule>,
    #[serde(default)]
    pub domains: Vec<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BlocklistEntry {
    pub domain: String,
    #[serde(default)]
    pub description: Option<String>,
    #[serde(default = "default_unblock_delay")]
    pub unblock_delay: String,
    pub schedule: Option<Schedule>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AllowlistEntry {
    pub domain: String,
    #[serde(default)]
    pub description: Option<String>,
}

/// Schedule definition with available hours per day group.
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

/// Notifications configuration (stored separately or in env).
#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct NotificationsConfig {
    pub discord: Option<DiscordConfig>,
    pub telegram: Option<TelegramConfig>,
    pub slack: Option<SlackConfig>,
    pub ntfy: Option<NtfyConfig>,
    pub macos: Option<MacosNotifyConfig>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DiscordConfig {
    pub webhook_url: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TelegramConfig {
    pub bot_token: String,
    pub chat_id: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SlackConfig {
    pub webhook_url: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct NtfyConfig {
    pub url: String,
    pub topic: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MacosNotifyConfig {
    pub enabled: bool,
}

/// Environment-based secrets (not in config.json).
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
