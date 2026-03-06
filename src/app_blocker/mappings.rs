/// Known domain-to-app mappings for common services.
/// Each entry: (domain, bundle_id, app_name)
pub const KNOWN_MAPPINGS: &[(&str, &str, &str)] = &[
    // Messaging
    ("whatsapp.com", "net.whatsapp.WhatsApp", "WhatsApp"),
    ("web.whatsapp.com", "net.whatsapp.WhatsApp", "WhatsApp"),
    ("discord.com", "com.hnc.Discord", "Discord"),
    ("discord.gg", "com.hnc.Discord", "Discord"),
    ("telegram.org", "ru.keepcoder.Telegram", "Telegram"),
    ("t.me", "ru.keepcoder.Telegram", "Telegram"),
    ("slack.com", "com.tinyspeck.slackmacgap", "Slack"),
    ("signal.org", "org.whispersystems.signal-desktop", "Signal"),
    // Social
    ("twitter.com", "com.atebits.Tweetie2", "Twitter"),
    ("x.com", "com.atebits.Tweetie2", "Twitter"),
    ("instagram.com", "com.burbn.instagram", "Instagram"),
    ("reddit.com", "com.reddit.Reddit", "Reddit"),
    ("tiktok.com", "com.zhiliaoapp.musically", "TikTok"),
    ("facebook.com", "com.facebook.Facebook", "Facebook"),
    ("messenger.com", "com.facebook.archon", "Messenger"),
    // Entertainment
    ("spotify.com", "com.spotify.client", "Spotify"),
    ("netflix.com", "com.netflix.Netflix", "Netflix"),
    ("twitch.tv", "tv.twitch.desktop", "Twitch"),
    // Productivity (sometimes distraction)
    ("notion.so", "notion.id", "Notion"),
    ("figma.com", "com.figma.Desktop", "Figma"),
];

/// Find known mappings for a domain (exact match).
pub fn lookup_domain(domain: &str) -> Vec<(&'static str, &'static str)> {
    KNOWN_MAPPINGS
        .iter()
        .filter(|(d, _, _)| *d == domain)
        .map(|(_, bundle_id, app_name)| (*bundle_id, *app_name))
        .collect()
}

/// Find known mappings for a bundle ID.
pub fn lookup_bundle(bundle_id: &str) -> Vec<(&'static str, &'static str)> {
    KNOWN_MAPPINGS
        .iter()
        .filter(|(_, b, _)| *b == bundle_id)
        .map(|(domain, _, app_name)| (*domain, *app_name))
        .collect()
}
