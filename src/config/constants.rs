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

/// NextDNS native services that can be blocked.
pub const NEXTDNS_SERVICES: &[(&str, &str)] = &[
    ("tiktok", "TikTok"),
    ("instagram", "Instagram"),
    ("facebook", "Facebook"),
    ("snapchat", "Snapchat"),
    ("twitter", "Twitter / X"),
    ("reddit", "Reddit"),
    ("youtube", "YouTube"),
    ("netflix", "Netflix"),
    ("disney-plus", "Disney+"),
    ("hbo-max", "HBO Max"),
    ("amazon-prime-video", "Amazon Prime Video"),
    ("twitch", "Twitch"),
    ("spotify", "Spotify"),
    ("fortnite", "Fortnite"),
    ("roblox", "Roblox"),
    ("minecraft", "Minecraft"),
    ("discord", "Discord"),
    ("telegram", "Telegram"),
    ("whatsapp", "WhatsApp"),
    ("signal", "Signal"),
    ("pinterest", "Pinterest"),
    ("tumblr", "Tumblr"),
    ("imgur", "Imgur"),
    ("9gag", "9GAG"),
    ("vimeo", "Vimeo"),
    ("dailymotion", "Dailymotion"),
    ("ebay", "eBay"),
    ("amazon", "Amazon"),
    ("aliexpress", "AliExpress"),
    ("wish", "Wish"),
    ("steam", "Steam"),
    ("epic-games", "Epic Games"),
    ("league-of-legends", "League of Legends"),
    ("blizzard-entertainment", "Blizzard Entertainment"),
    ("tinder", "Tinder"),
    ("bumble", "Bumble"),
    ("hinge", "Hinge"),
    ("chatgpt", "ChatGPT"),
    ("character-ai", "Character.AI"),
    ("bing-ai", "Bing AI"),
    ("threads", "Threads"),
    ("mastodon", "Mastodon"),
    ("bluesky", "Bluesky"),
    ("bereal", "BeReal"),
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

/// PIN session duration in seconds (30 minutes).
pub const PIN_SESSION_DURATION_SECS: i64 = 1800;

/// PIN lockout duration in seconds (15 minutes).
pub const PIN_LOCKOUT_DURATION_SECS: i64 = 900;

/// Maximum PIN attempts before lockout.
pub const PIN_MAX_ATTEMPTS: i32 = 3;
