/// NextDNS native parental control categories.
pub const NEXTDNS_CATEGORIES: &[(&str, &str)] = &[
    ("gambling", "Gambling & Betting"),
    ("dating", "Dating"),
    ("piracy", "Piracy"),
    ("porn", "Pornography"),
    ("social-networks", "Social Networks"),
    ("gaming", "Gaming"),
    ("video-streaming", "Video Streaming"),
];

/// Default rate limit: requests per window.
pub const DEFAULT_RATE_LIMIT_REQUESTS: u32 = 30;

/// Default rate limit window in seconds.
pub const DEFAULT_RATE_LIMIT_WINDOW_SECS: u64 = 60;

/// Default circuit breaker failure threshold.
pub const DEFAULT_CB_FAILURE_THRESHOLD: u32 = 5;

/// Default circuit breaker reset timeout in seconds.
pub const DEFAULT_CB_RESET_TIMEOUT_SECS: u64 = 60;

/// Default API cache TTL in seconds.
pub const DEFAULT_CACHE_TTL_SECS: u64 = 300;

/// Maximum retry attempts for failed API operations.
pub const MAX_RETRY_ATTEMPTS: i32 = 5;

/// Base delay for exponential backoff (seconds).
pub const RETRY_BASE_DELAY_SECS: u64 = 1;

/// Maximum delay for exponential backoff (seconds).
pub const RETRY_MAX_DELAY_SECS: u64 = 30;

