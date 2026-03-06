use serde::{Deserialize, Serialize};

/// API response for denylist entries.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DenylistEntry {
    pub id: String,
    pub active: bool,
}

/// API response for allowlist entries.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AllowlistEntry {
    pub id: String,
    pub active: bool,
}

/// API response for parental control categories.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ParentalCategory {
    pub id: String,
    pub active: bool,
}

/// API response for parental control services.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ParentalService {
    pub id: String,
    pub active: bool,
}

/// Generic API result type.
pub type ApiResult<T> = Result<T, crate::error::AppError>;
