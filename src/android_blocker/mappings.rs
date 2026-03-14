/// Known domain-to-Android-package mappings for common services.
/// Each entry: (domain, package_name, display_name)
pub const ANDROID_PACKAGES: &[(&str, &str, &str)] = &[
    // Messaging
    ("whatsapp.com", "com.whatsapp", "WhatsApp"),
    ("web.whatsapp.com", "com.whatsapp", "WhatsApp"),
    ("discord.com", "com.discord", "Discord"),
    ("discord.gg", "com.discord", "Discord"),
    ("telegram.org", "org.telegram.messenger", "Telegram"),
    ("t.me", "org.telegram.messenger", "Telegram"),
    ("slack.com", "com.Slack", "Slack"),
    ("signal.org", "org.thoughtcrime.securesms", "Signal"),
    ("messenger.com", "com.facebook.orca", "Messenger"),
    // Social
    ("twitter.com", "com.twitter.android", "Twitter"),
    ("x.com", "com.twitter.android", "Twitter"),
    ("instagram.com", "com.instagram.android", "Instagram"),
    ("reddit.com", "com.reddit.frontpage", "Reddit"),
    ("tiktok.com", "com.zhiliaoapp.musically", "TikTok"),
    ("facebook.com", "com.facebook.katana", "Facebook"),
    ("snapchat.com", "com.snapchat.android", "Snapchat"),
    ("pinterest.com", "com.pinterest", "Pinterest"),
    ("linkedin.com", "com.linkedin.android", "LinkedIn"),
    // Entertainment
    ("youtube.com", "com.google.android.youtube", "YouTube"),
    ("netflix.com", "com.netflix.mediaclient", "Netflix"),
    ("twitch.tv", "tv.twitch.android.app", "Twitch"),
    ("spotify.com", "com.spotify.music", "Spotify"),
];

/// Find known Android packages for a domain (exact match).
pub fn lookup_domain(domain: &str) -> Vec<(&'static str, &'static str)> {
    ANDROID_PACKAGES
        .iter()
        .filter(|(d, _, _)| *d == domain)
        .map(|(_, package_name, display_name)| (*package_name, *display_name))
        .collect()
}

/// Mapping from NextDNS category IDs to Android packages.
/// Each entry: (category_id, package_name, display_name)
pub const CATEGORY_PACKAGES: &[(&str, &str, &str)] = &[
    // social-networks
    ("social-networks", "com.instagram.android", "Instagram"),
    ("social-networks", "com.facebook.katana", "Facebook"),
    ("social-networks", "com.facebook.orca", "Messenger"),
    ("social-networks", "com.snapchat.android", "Snapchat"),
    ("social-networks", "com.twitter.android", "Twitter"),
    ("social-networks", "com.zhiliaoapp.musically", "TikTok"),
    ("social-networks", "com.pinterest", "Pinterest"),
    ("social-networks", "com.linkedin.android", "LinkedIn"),
    ("social-networks", "com.reddit.frontpage", "Reddit"),
    ("social-networks", "com.whatsapp", "WhatsApp"),
    ("social-networks", "org.telegram.messenger", "Telegram"),
    ("social-networks", "org.thoughtcrime.securesms", "Signal"),
    ("social-networks", "com.discord", "Discord"),
    ("social-networks", "com.Slack", "Slack"),
    // video-streaming
    ("video-streaming", "com.google.android.youtube", "YouTube"),
    ("video-streaming", "com.netflix.mediaclient", "Netflix"),
    ("video-streaming", "tv.twitch.android.app", "Twitch"),
    ("video-streaming", "com.spotify.music", "Spotify"),
    ("video-streaming", "com.amazon.avod.thirdpartyclient", "Prime Video"),
    ("video-streaming", "com.disney.disneyplus", "Disney+"),
    ("video-streaming", "com.hbo.hbonow", "HBO Max"),
    // gaming
    ("gaming", "com.epicgames.fortnite", "Fortnite"),
    ("gaming", "com.roblox.client", "Roblox"),
    ("gaming", "com.mojang.minecraftpe", "Minecraft"),
    ("gaming", "com.valvesoftware.android.steam.community", "Steam"),
    // dating
    ("dating", "com.tinder", "Tinder"),
    ("dating", "com.bumble.app", "Bumble"),
    ("dating", "co.hinge.app", "Hinge"),
    // gambling
    ("gambling", "com.draftkings.sportsbook", "DraftKings"),
    ("gambling", "com.fanduel.sportsbook", "FanDuel"),
];

/// Get all Android packages for a NextDNS category.
pub fn packages_for_category(category_id: &str) -> Vec<(&'static str, &'static str)> {
    CATEGORY_PACKAGES
        .iter()
        .filter(|(cat, _, _)| *cat == category_id)
        .map(|(_, pkg, name)| (*pkg, *name))
        .collect()
}

/// Find which domains in ANDROID_PACKAGES map to a given package.
pub fn domains_for_package(package: &str) -> Vec<&'static str> {
    ANDROID_PACKAGES
        .iter()
        .filter(|(_, p, _)| *p == package)
        .map(|(d, _, _)| *d)
        .collect()
}
