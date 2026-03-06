use serde::{Deserialize, Serialize};

/// A validated domain name.
#[derive(Debug, Clone, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub struct Domain(String);

impl Domain {
    /// Create a new Domain, validating RFC 1123 format.
    pub fn new(s: &str) -> Result<Self, DomainError> {
        let s = s.trim().to_lowercase();

        if s.is_empty() {
            return Err(DomainError::Empty);
        }
        if s.len() > 253 {
            return Err(DomainError::TooLong(s.len()));
        }

        let labels: Vec<&str> = s.split('.').collect();
        if labels.len() < 2 {
            return Err(DomainError::InvalidFormat(s));
        }

        for label in &labels {
            if label.is_empty() || label.len() > 63 {
                return Err(DomainError::InvalidLabel(label.to_string()));
            }
            if label.starts_with('-') || label.ends_with('-') {
                return Err(DomainError::InvalidLabel(label.to_string()));
            }
            if !label.chars().all(|c| c.is_ascii_alphanumeric() || c == '-') {
                return Err(DomainError::InvalidCharacter(label.to_string()));
            }
        }

        Ok(Self(s))
    }

    pub fn as_str(&self) -> &str {
        &self.0
    }
}

impl std::fmt::Display for Domain {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.write_str(&self.0)
    }
}

impl AsRef<str> for Domain {
    fn as_ref(&self) -> &str {
        &self.0
    }
}

#[derive(Debug, thiserror::Error)]
pub enum DomainError {
    #[error("Domain cannot be empty")]
    Empty,
    #[error("Domain too long: {0} chars (max 253)")]
    TooLong(usize),
    #[error("Invalid domain format: {0}")]
    InvalidFormat(String),
    #[error("Invalid label: {0}")]
    InvalidLabel(String),
    #[error("Invalid character in label: {0}")]
    InvalidCharacter(String),
}

/// Blocked domain entry.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BlockedDomain {
    pub id: i64,
    pub domain: String,
    pub active: bool,
    pub description: Option<String>,
    pub category: Option<String>,
    pub schedule: Option<String>,
    pub created_at: i64,
    pub updated_at: i64,
}

/// Allowed domain entry.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AllowedDomain {
    pub id: i64,
    pub domain: String,
    pub active: bool,
    pub description: Option<String>,
    pub created_at: i64,
    pub updated_at: i64,
}

/// Category for grouping domains.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Category {
    pub id: i64,
    pub name: String,
    pub description: Option<String>,
    pub schedule: Option<String>,
    pub is_locked: bool,
    pub created_at: i64,
    pub updated_at: i64,
}

/// NextDNS native category.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct NextDnsCategory {
    pub id: String,
    pub active: bool,
    pub created_at: i64,
}

/// NextDNS native service.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct NextDnsService {
    pub id: String,
    pub active: bool,
    pub created_at: i64,
}

/// Pending action to be executed.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PendingAction {
    pub id: String,
    pub action: String,
    pub domain: Option<String>,
    pub list_type: String,
    pub scheduled_at: i64,
    pub execute_at: i64,
    pub status: String,
    pub description: Option<String>,
    pub created_at: i64,
}

/// Retry queue entry for failed API operations.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RetryEntry {
    pub id: String,
    pub action: String,
    pub domain: Option<String>,
    pub list_type: String,
    pub payload: Option<String>,
    pub attempts: i32,
    pub max_attempts: i32,
    pub last_error: Option<String>,
    pub next_retry_at: i64,
    pub created_at: i64,
}

/// Unlock request for protected items.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct UnlockRequest {
    pub id: String,
    pub target_type: String,
    pub target_id: String,
    pub reason: String,
    pub status: String,
    pub requested_at: i64,
    pub resolved_at: Option<i64>,
}

/// Audit log entry.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AuditEntry {
    pub id: i64,
    pub action: String,
    pub target_type: String,
    pub target_id: String,
    pub details: Option<String>,
    pub timestamp: i64,
}

/// Daily statistics.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DailyStats {
    pub date: String,
    pub domains_blocked: i32,
    pub domains_allowed: i32,
    pub sync_count: i32,
    pub api_errors: i32,
}
