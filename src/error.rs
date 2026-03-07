use std::fmt;

use serde::Serialize;

/// Exit codes for structured LLM consumption.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize)]
#[repr(u8)]
pub enum ExitCode {
    Success = 0,
    GeneralError = 1,
    ConfigError = 2,
    ApiError = 3,
    ValidationError = 4,

    ConflictError = 6,
    NotFound = 7,
    Interrupted = 130,
}

impl ExitCode {
    pub fn as_u8(self) -> u8 {
        self as u8
    }

    pub fn name(self) -> &'static str {
        match self {
            Self::Success => "success",
            Self::GeneralError => "general_error",
            Self::ConfigError => "config_error",
            Self::ApiError => "api_error",
            Self::ValidationError => "validation_error",

            Self::ConflictError => "conflict_error",
            Self::NotFound => "not_found",
            Self::Interrupted => "interrupted",
        }
    }
}

impl fmt::Display for ExitCode {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "{}", self.name())
    }
}

impl From<ExitCode> for std::process::ExitCode {
    fn from(code: ExitCode) -> Self {
        std::process::ExitCode::from(code.as_u8())
    }
}

/// Application error type with structured error information.
#[derive(Debug, thiserror::Error)]
pub enum AppError {
    #[error("Configuration error: {message}")]
    Config {
        message: String,
        hint: Option<String>,
    },

    #[error("API error: {message}")]
    Api {
        message: String,
        status_code: Option<u16>,
        hint: Option<String>,
    },

    #[error("Validation error: {message}")]
    Validation {
        message: String,
        details: Vec<ValidationDetail>,
        hint: Option<String>,
    },

    #[error("Conflict: {message}")]
    Conflict {
        message: String,
        hint: Option<String>,
    },

    #[error("Not found: {message}")]
    NotFound {
        message: String,
        hint: Option<String>,
    },

    #[error("Database error: {source}")]
    Database {
        #[from]
        source: rusqlite::Error,
    },

    #[error("IO error: {source}")]
    Io {
        #[from]
        source: std::io::Error,
    },

    #[error("JSON error: {source}")]
    Json {
        #[from]
        source: serde_json::Error,
    },

    #[error("{message}")]
    General {
        message: String,
        hint: Option<String>,
    },
}

#[derive(Debug, Clone, Serialize)]
pub struct ValidationDetail {
    pub field: String,
    pub reason: String,
}

impl AppError {
    pub fn exit_code(&self) -> ExitCode {
        match self {
            Self::Config { .. } => ExitCode::ConfigError,
            Self::Api { .. } => ExitCode::ApiError,
            Self::Validation { .. } => ExitCode::ValidationError,
            Self::Conflict { .. } => ExitCode::ConflictError,
            Self::NotFound { .. } => ExitCode::NotFound,
            Self::Database { .. } | Self::Io { .. } | Self::Json { .. } | Self::General { .. } => {
                ExitCode::GeneralError
            }
        }
    }

    pub fn hint(&self) -> Option<&str> {
        match self {
            Self::Config { hint, .. }
            | Self::Api { hint, .. }
            | Self::Validation { hint, .. }
            | Self::Conflict { hint, .. }
            | Self::NotFound { hint, .. }
            | Self::General { hint, .. } => hint.as_deref(),
            Self::Database { .. } => Some("Check database file permissions and integrity"),
            Self::Io { .. } => Some("Check file permissions and disk space"),
            Self::Json { .. } => Some("Check input format"),
        }
    }

    pub fn error_code(&self) -> &str {
        match self {
            Self::Config { .. } => "config_error",
            Self::Api { .. } => "api_error",
            Self::Validation { .. } => "validation_error",
            Self::Conflict { .. } => "conflict_error",
            Self::NotFound { .. } => "not_found",
            Self::Database { .. } => "database_error",
            Self::Io { .. } => "io_error",
            Self::Json { .. } => "json_error",
            Self::General { .. } => "general_error",
        }
    }

    pub fn to_json(&self, command: &str) -> serde_json::Value {
        let mut error = serde_json::json!({
            "code": self.error_code(),
            "message": self.to_string(),
        });

        if let Some(hint) = self.hint() {
            error["hint"] = serde_json::Value::String(hint.to_string());
        }

        if let Self::Validation { details, .. } = self {
            error["details"] = serde_json::to_value(details)
                .unwrap_or_else(|_| serde_json::Value::Array(vec![]));
        }

        if let Self::Api { status_code: Some(code), .. } = self {
            error["status_code"] = serde_json::json!(code);
        }

        serde_json::json!({
            "ok": false,
            "command": command,
            "error": error,
            "exit_code": self.exit_code().as_u8(),
            "timestamp": chrono::Utc::now().to_rfc3339_opts(chrono::SecondsFormat::Secs, true),
        })
    }
}

impl AppError {
    /// Returns true for authentication/authorization errors (401, 403) that should not be retried.
    pub fn is_auth_error(&self) -> bool {
        matches!(self, Self::Api { status_code: Some(401 | 403), .. })
    }
}

pub type AppResult<T> = Result<T, AppError>;
