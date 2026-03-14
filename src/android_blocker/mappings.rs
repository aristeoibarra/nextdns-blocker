/// Known domain-to-Android-package mappings for common services.
/// Each entry: (domain, package_name, display_name)
///
/// Source: https://github.com/nextdns/services (official curated domain lists per service)
/// Only main user-facing domains included (not CDN/API subdomains).
pub const ANDROID_PACKAGES: &[(&str, &str, &str)] = &[
    // === Messaging ===
    ("whatsapp.com", "com.whatsapp", "WhatsApp"),
    ("web.whatsapp.com", "com.whatsapp", "WhatsApp"),
    ("discord.com", "com.discord", "Discord"),
    ("discord.gg", "com.discord", "Discord"),
    ("discordapp.com", "com.discord", "Discord"),
    ("telegram.org", "org.telegram.messenger", "Telegram"),
    ("t.me", "org.telegram.messenger", "Telegram"),
    ("slack.com", "com.Slack", "Slack"),
    ("signal.org", "org.thoughtcrime.securesms", "Signal"),
    ("messenger.com", "com.facebook.orca", "Messenger"),
    ("zoom.us", "us.zoom.videomeetings", "Zoom"),
    ("zoom.com", "us.zoom.videomeetings", "Zoom"),
    ("skype.com", "com.skype.raider", "Skype"),

    // === Social ===
    ("twitter.com", "com.twitter.android", "Twitter"),
    ("x.com", "com.twitter.android", "Twitter"),
    ("instagram.com", "com.instagram.android", "Instagram"),
    ("threads.net", "com.instagram.barcelona", "Threads"),
    ("reddit.com", "com.reddit.frontpage", "Reddit"),
    ("tiktok.com", "com.zhiliaoapp.musically", "TikTok"),
    ("facebook.com", "com.facebook.katana", "Facebook"),
    ("fb.com", "com.facebook.katana", "Facebook"),
    ("snapchat.com", "com.snapchat.android", "Snapchat"),
    ("pinterest.com", "com.pinterest", "Pinterest"),
    ("linkedin.com", "com.linkedin.android", "LinkedIn"),
    ("tumblr.com", "com.tumblr", "Tumblr"),
    ("bsky.app", "xyz.blueskyweb.app", "Bluesky"),
    ("bsky.social", "xyz.blueskyweb.app", "Bluesky"),
    ("mastodon.social", "org.joinmastodon.android", "Mastodon"),
    ("bereal.com", "com.bereal.ft", "BeReal"),
    ("bere.al", "com.bereal.ft", "BeReal"),
    ("9gag.com", "com.ninegag.android.app", "9GAG"),
    ("vk.com", "com.vkontakte.android", "VK"),

    // === Video & Audio Streaming ===
    ("youtube.com", "com.google.android.youtube", "YouTube"),
    ("youtu.be", "com.google.android.youtube", "YouTube"),
    ("netflix.com", "com.netflix.mediaclient", "Netflix"),
    ("twitch.tv", "tv.twitch.android.app", "Twitch"),
    ("spotify.com", "com.spotify.music", "Spotify"),
    ("disneyplus.com", "com.disney.disneyplus", "Disney+"),
    ("disney-plus.net", "com.disney.disneyplus", "Disney+"),
    ("hbomax.com", "com.hbo.hbonow", "Max"),
    ("max.com", "com.hbo.hbonow", "Max"),
    ("hulu.com", "com.hulu.plus", "Hulu"),
    ("primevideo.com", "com.amazon.avod.thirdpartyclient", "Prime Video"),
    ("vimeo.com", "com.vimeo.android.videoapp", "Vimeo"),
    ("dailymotion.com", "com.dailymotion.dailymotion", "Dailymotion"),
    ("crunchyroll.com", "com.crunchyroll.crunchyroid", "Crunchyroll"),
    ("rumble.com", "com.rumble.battles", "Rumble"),
    ("pandora.com", "com.pandora.android", "Pandora"),
    ("deezer.com", "deezer.android.app", "Deezer"),
    ("tidal.com", "com.aspiro.tidal", "TIDAL"),
    ("soundcloud.com", "com.soundcloud.android", "SoundCloud"),
    ("pluto.tv", "tv.pluto.android", "Pluto TV"),
    ("peacocktv.com", "com.peacocktv.peacockandroid", "Peacock"),
    ("paramountplus.com", "com.cbs.ott", "Paramount+"),
    ("podcasts.apple.com", "com.apple.android.music", "Apple Music"),

    // === Gaming ===
    ("epicgames.com", "com.epicgames.fortnite", "Fortnite"),
    ("roblox.com", "com.roblox.client", "Roblox"),
    ("minecraft.net", "com.mojang.minecraftpe", "Minecraft"),
    ("mojang.com", "com.mojang.minecraftpe", "Minecraft"),
    ("steampowered.com", "com.valvesoftware.android.steam.community", "Steam"),
    ("steamcommunity.com", "com.valvesoftware.android.steam.community", "Steam"),
    ("battle.net", "com.blizzard.wtcg.hearthstone", "Blizzard"),
    ("blizzard.com", "com.blizzard.wtcg.hearthstone", "Blizzard"),
    ("leagueoflegends.com", "com.riotgames.league.wildrift", "League of Legends"),
    ("playstation.net", "com.playstation.app", "PlayStation"),
    ("xbox.com", "com.microsoft.xboxone.smartglass", "Xbox"),

    // === Dating ===
    ("tinder.com", "com.tinder", "Tinder"),
    ("gotinder.com", "com.tinder", "Tinder"),
    ("bumble.com", "com.bumble.app", "Bumble"),
    ("hinge.co", "co.hinge.app", "Hinge"),
    ("badoo.com", "com.badoo.mobile", "Badoo"),
    ("okcupid.com", "com.okcupid.okcupid", "OkCupid"),
    ("match.com", "com.match.android.matchmobile", "Match"),
    ("grindr.com", "com.grindr.android", "Grindr"),
    ("happn.com", "com.ftw_and_co.happn", "Happn"),
    ("pof.com", "com.pof.android", "Plenty of Fish"),
    ("plentyoffish.com", "com.pof.android", "Plenty of Fish"),
    ("coffeemeetsbagel.com", "com.coffeemeetsbagel.android", "Coffee Meets Bagel"),
    ("eharmony.com", "com.eharmony", "eHarmony"),
    ("zoosk.com", "com.zoosk.zoosk", "Zoosk"),
    ("feeld.co", "co.feeld.app", "Feeld"),
    ("taimi.com", "com.taimi", "Taimi"),
    ("chispa-app.com", "com.matchgroup.chispa", "Chispa"),
    ("meetme.com", "com.myyearbook.m", "MeetMe"),
    ("waplog.com", "com.waplog.social", "Waplog"),
    ("jaumo.com", "com.jaumo", "Jaumo"),

    // === Gambling ===
    ("draftkings.com", "com.draftkings.sportsbook", "DraftKings"),
    ("fanduel.com", "com.fanduel.sportsbook", "FanDuel"),
    ("betmgm.com", "com.betmgm.sportsbook", "BetMGM"),
    ("caesars.com", "com.williamhill.sportsbook.wh", "Caesars Sportsbook"),
    ("bet365.com", "com.bet365app", "bet365"),
    ("pointsbet.com", "com.pointsbet.sportsbook", "PointsBet"),
    ("betway.com", "com.betway.app", "Betway"),
    ("unibet.com", "com.kindredgroup.unibet", "Unibet"),
    ("stake.com", "com.stake.app", "Stake"),
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
///
/// Sources:
/// - https://github.com/nextdns/services (official curated domain lists)
/// - https://github.com/nickel-lang/olbat-ut1-blacklists (UT1 category lists used by NextDNS)
/// - https://github.com/nextdns/metadata/issues/242 (social-networks excludes messaging)
///
/// NextDNS "social-networks" does NOT block messaging apps (WhatsApp, Telegram,
/// Signal, Discord, Slack, Messenger). Confirmed excluded since June 2020.
///
/// Package names verified against Google Play Store (March 2026).
pub const CATEGORY_PACKAGES: &[(&str, &str, &str)] = &[
    // ========================================================================
    // social-networks (no messaging apps — NextDNS explicitly excludes them)
    // Base: UT1 social_networks/domains (715 domains)
    // ========================================================================
    ("social-networks", "com.instagram.android", "Instagram"),
    ("social-networks", "com.instagram.barcelona", "Threads"),
    ("social-networks", "com.facebook.katana", "Facebook"),
    ("social-networks", "com.snapchat.android", "Snapchat"),
    ("social-networks", "com.twitter.android", "Twitter"),
    ("social-networks", "com.zhiliaoapp.musically", "TikTok"),
    ("social-networks", "com.pinterest", "Pinterest"),
    ("social-networks", "com.linkedin.android", "LinkedIn"),
    ("social-networks", "com.reddit.frontpage", "Reddit"),
    ("social-networks", "com.tumblr", "Tumblr"),
    ("social-networks", "com.vkontakte.android", "VK"),
    ("social-networks", "com.bereal.ft", "BeReal"),
    ("social-networks", "org.joinmastodon.android", "Mastodon"),
    ("social-networks", "xyz.blueskyweb.app", "Bluesky"),
    ("social-networks", "com.ninegag.android.app", "9GAG"),
    ("social-networks", "com.lemon8.android", "Lemon8"),

    // ========================================================================
    // video-streaming
    // Base: nextdns/piracy-blocklists/streaming-video + legit service inclusions
    // ========================================================================
    ("video-streaming", "com.google.android.youtube", "YouTube"),
    ("video-streaming", "com.google.android.apps.youtube.kids", "YouTube Kids"),
    ("video-streaming", "com.netflix.mediaclient", "Netflix"),
    ("video-streaming", "tv.twitch.android.app", "Twitch"),
    ("video-streaming", "com.spotify.music", "Spotify"),
    ("video-streaming", "com.amazon.avod.thirdpartyclient", "Prime Video"),
    ("video-streaming", "com.disney.disneyplus", "Disney+"),
    ("video-streaming", "com.hbo.hbonow", "Max"),
    ("video-streaming", "com.hulu.plus", "Hulu"),
    ("video-streaming", "com.vimeo.android.videoapp", "Vimeo"),
    ("video-streaming", "com.dailymotion.dailymotion", "Dailymotion"),
    ("video-streaming", "com.crunchyroll.crunchyroid", "Crunchyroll"),
    ("video-streaming", "com.rumble.battles", "Rumble"),
    ("video-streaming", "tv.pluto.android", "Pluto TV"),
    ("video-streaming", "com.peacocktv.peacockandroid", "Peacock"),
    ("video-streaming", "com.cbs.ott", "Paramount+"),
    ("video-streaming", "com.pandora.android", "Pandora"),
    ("video-streaming", "deezer.android.app", "Deezer"),
    ("video-streaming", "com.aspiro.tidal", "TIDAL"),
    ("video-streaming", "com.soundcloud.android", "SoundCloud"),

    // ========================================================================
    // gaming
    // Base: UT1 games/domains (33,694 domains)
    // ========================================================================
    ("gaming", "com.epicgames.fortnite", "Fortnite"),
    ("gaming", "com.epicgames.portal", "Epic Games Store"),
    ("gaming", "com.roblox.client", "Roblox"),
    ("gaming", "com.mojang.minecraftpe", "Minecraft"),
    ("gaming", "com.valvesoftware.android.steam.community", "Steam"),
    ("gaming", "com.blizzard.wtcg.hearthstone", "Hearthstone"),
    ("gaming", "com.activision.callofduty.shooter", "Call of Duty Mobile"),
    ("gaming", "com.riotgames.league.wildrift", "League of Legends"),
    ("gaming", "com.playstation.app", "PlayStation"),
    ("gaming", "com.microsoft.xboxone.smartglass", "Xbox"),
    ("gaming", "com.supercell.clashofclans", "Clash of Clans"),
    ("gaming", "com.supercell.clashroyale", "Clash Royale"),
    ("gaming", "com.supercell.brawlstars", "Brawl Stars"),
    ("gaming", "com.tencent.ig", "PUBG Mobile"),
    ("gaming", "com.miHoYo.GenshinImpact", "Genshin Impact"),
    ("gaming", "com.garena.game.codm", "Free Fire"),
    ("gaming", "com.innersloth.spacemafia", "Among Us"),
    ("gaming", "com.king.candycrushsaga", "Candy Crush"),
    ("gaming", "com.ea.gp.fifamobile", "EA FC Mobile"),
    ("gaming", "com.dts.freefireth", "Free Fire MAX"),
    ("gaming", "com.kabam.marvelbattle", "Marvel Contest"),
    ("gaming", "com.nianticlabs.pokemongo", "Pokemon GO"),

    // ========================================================================
    // dating
    // Base: UT1 dating/domains (6,488 domains)
    // ========================================================================
    ("dating", "com.tinder", "Tinder"),
    ("dating", "com.bumble.app", "Bumble"),
    ("dating", "co.hinge.app", "Hinge"),
    ("dating", "com.badoo.mobile", "Badoo"),
    ("dating", "com.okcupid.okcupid", "OkCupid"),
    ("dating", "com.match.android.matchmobile", "Match"),
    ("dating", "com.grindr.android", "Grindr"),
    ("dating", "com.ftw_and_co.happn", "Happn"),
    ("dating", "com.pof.android", "Plenty of Fish"),
    ("dating", "com.coffeemeetsbagel.android", "Coffee Meets Bagel"),
    ("dating", "com.eharmony", "eHarmony"),
    ("dating", "com.zoosk.zoosk", "Zoosk"),
    ("dating", "co.feeld.app", "Feeld"),
    ("dating", "com.taimi", "Taimi"),
    ("dating", "com.matchgroup.chispa", "Chispa"),
    ("dating", "com.myyearbook.m", "MeetMe"),
    ("dating", "com.spark.lovoo", "LOVOO"),
    ("dating", "com.waplog.social", "Waplog"),
    ("dating", "com.jaumo", "Jaumo"),

    // ========================================================================
    // gambling
    // Base: UT1 gambling/domains (32,236) + Sinfonietta gambling-hosts (2,639)
    // ========================================================================
    ("gambling", "com.draftkings.sportsbook", "DraftKings"),
    ("gambling", "com.draftkings.casino", "DraftKings Casino"),
    ("gambling", "com.fanduel.sportsbook", "FanDuel"),
    ("gambling", "com.fanduel.casino", "FanDuel Casino"),
    ("gambling", "com.betmgm.sportsbook", "BetMGM"),
    ("gambling", "com.williamhill.sportsbook.wh", "Caesars Sportsbook"),
    ("gambling", "com.bet365app", "bet365"),
    ("gambling", "com.pointsbet.sportsbook", "PointsBet"),
    ("gambling", "com.betway.app", "Betway"),
    ("gambling", "com.kindredgroup.unibet", "Unibet"),
    ("gambling", "com.stake.app", "Stake"),
    ("gambling", "com.pokerstars.eu", "PokerStars"),
    ("gambling", "com.betfair.sportsbook", "Betfair"),
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
