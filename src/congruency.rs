use crate::android_blocker::mappings;
use crate::db::Database;
use crate::error::AppError;

/// Domains that belong to the same service.
/// Used to detect contradictions like youtu.be in allowlist while youtube.com is blocked.
const SERVICE_DOMAINS: &[(&str, &[&str])] = &[
    ("youtube", &["youtube.com", "youtu.be", "yt3.ggpht.com", "ytimg.com"]),
    ("netflix", &["netflix.com", "nflxvideo.net", "nflximg.net", "nflxso.net", "nflxext.com"]),
    ("twitter", &["twitter.com", "x.com", "t.co", "twimg.com"]),
    ("discord", &["discord.com", "discord.gg", "discordapp.com", "discord.media"]),
    ("reddit", &["reddit.com", "redd.it", "redditstatic.com", "redditmedia.com"]),
    ("twitch", &["twitch.tv", "twitchcdn.net", "jtvnw.net", "ttvnw.net"]),
    ("telegram", &["telegram.org", "t.me"]),
    ("whatsapp", &["whatsapp.com", "web.whatsapp.com"]),
    ("facebook", &["facebook.com", "messenger.com"]),
    ("instagram", &["instagram.com"]),
    ("tiktok", &["tiktok.com"]),
    ("snapchat", &["snapchat.com"]),
    ("spotify", &["spotify.com"]),
    ("pinterest", &["pinterest.com"]),
    ("linkedin", &["linkedin.com"]),
    ("signal", &["signal.org"]),
    ("slack", &["slack.com"]),
];

#[derive(Debug, serde::Serialize)]
pub struct Issue {
    pub code: &'static str,
    pub severity: &'static str,
    pub domain: String,
    pub message: String,
    pub suggestion: String,
}

/// Find which service a domain belongs to.
fn service_for_domain(domain: &str) -> Option<(&'static str, &'static [&'static str])> {
    SERVICE_DOMAINS.iter().find(|(_, domains)| domains.contains(&domain)).map(|(svc, domains)| (*svc, *domains))
}

/// Find which NextDNS category covers a domain (via package mappings).
fn category_covering_domain(domain: &str, active_categories: &[String]) -> Option<String> {
    let packages = mappings::lookup_domain(domain);
    for (pkg, _) in &packages {
        for cat in active_categories {
            let cat_pkgs = mappings::packages_for_category(cat);
            if cat_pkgs.iter().any(|(p, _)| p == pkg) {
                return Some(cat.clone());
            }
        }
    }
    None
}

/// Check if a domain has sibling domains in a service group.
fn siblings_in_service(domain: &str) -> Vec<&'static str> {
    match service_for_domain(domain) {
        Some((_, domains)) => domains.iter().filter(|d| **d != domain).copied().collect(),
        None => Vec::new(),
    }
}

/// Run all congruency checks against current DB state.
pub fn audit(db: &Database) -> Result<Vec<Issue>, AppError> {
    let mut issues = Vec::new();

    let active_cats: Vec<String> = db
        .with_conn(crate::db::nextdns::list_nextdns_categories)?
        .into_iter()
        .filter(|c| c.active)
        .map(|c| c.id)
        .collect();

    let denylist = db.with_conn(|conn| crate::db::domains::list_blocked(conn, true))?;
    let allowlist = db.with_conn(|conn| crate::db::domains::list_allowed(conn, true))?;

    let denied_domains: std::collections::HashSet<&str> =
        denylist.iter().map(|d| d.domain.as_str()).collect();
    let _allowed_domains: std::collections::HashSet<&str> =
        allowlist.iter().map(|d| d.domain.as_str()).collect();

    // Check 1: REDUNDANT_DENYLIST — domain in denylist already covered by NextDNS category
    for entry in &denylist {
        if entry.schedule.is_some() {
            continue; // has schedule, check 2 handles this
        }
        if let Some(cat) = category_covering_domain(&entry.domain, &active_cats) {
            issues.push(Issue {
                code: "REDUNDANT_DENYLIST",
                severity: "warning",
                domain: entry.domain.clone(),
                message: format!(
                    "'{}' is already blocked by NextDNS category '{}'",
                    entry.domain, cat
                ),
                suggestion: format!(
                    "Remove from denylist: ndb denylist remove {}",
                    entry.domain
                ),
            });
        }
    }

    // Check 2: INEFFECTIVE_SCHEDULE — domain in denylist with schedule, but category blocks 24/7
    for entry in &denylist {
        if entry.schedule.is_none() {
            continue;
        }
        if let Some(cat) = category_covering_domain(&entry.domain, &active_cats) {
            issues.push(Issue {
                code: "INEFFECTIVE_SCHEDULE",
                severity: "error",
                domain: entry.domain.clone(),
                message: format!(
                    "'{}' has a schedule in denylist, but category '{}' blocks it 24/7. The schedule has no effect.",
                    entry.domain, cat
                ),
                suggestion: format!(
                    "Move to allowlist with the schedule: ndb denylist remove {} && ndb allowlist add {} --schedule '...'",
                    entry.domain, entry.domain
                ),
            });
        }
    }

    // Check 3: CONTRADICTORY_ALLOWLIST — domain in allowlist whose service is blocked
    for entry in &allowlist {
        let siblings = siblings_in_service(&entry.domain);
        for sibling in &siblings {
            if denied_domains.contains(sibling) {
                issues.push(Issue {
                    code: "CONTRADICTORY_ALLOWLIST",
                    severity: "error",
                    domain: entry.domain.clone(),
                    message: format!(
                        "'{}' is in allowlist but '{}' (same service) is in denylist",
                        entry.domain, sibling
                    ),
                    suggestion: format!(
                        "Remove '{}' from allowlist, or remove '{}' from denylist",
                        entry.domain, sibling
                    ),
                });
            }
        }
        // Also check: allowed domain's service is blocked by a category but the domain is not
        // in the allowlist for a good reason (e.g., CDN domains without schedule)
        if entry.schedule.is_none() {
            if let Some(cat) = category_covering_domain(&entry.domain, &active_cats) {
                // This is intentional if the user explicitly allowed it — but flag CDN domains
                let is_cdn = entry.domain.contains("cdn")
                    || entry.domain.contains("static")
                    || entry.domain.contains("img")
                    || entry.domain.contains("ggpht");
                if is_cdn {
                    issues.push(Issue {
                        code: "ORPHAN_CDN",
                        severity: "warning",
                        domain: entry.domain.clone(),
                        message: format!(
                            "'{}' looks like a CDN domain allowed while category '{}' blocks the main service",
                            entry.domain, cat
                        ),
                        suggestion: format!(
                            "Remove if the main service is blocked: ndb allowlist remove {}",
                            entry.domain
                        ),
                    });
                }
            }
        }
    }

    Ok(issues)
}

/// Check congruency for a single domain being added to the denylist.
/// Returns warnings to include in the handler output.
pub fn check_denylist_add(db: &Database, domain: &str, has_schedule: bool) -> Vec<Issue> {
    let active_cats: Vec<String> = db
        .with_conn(crate::db::nextdns::list_nextdns_categories)
        .unwrap_or_default()
        .into_iter()
        .filter(|c| c.active)
        .map(|c| c.id)
        .collect();

    let mut issues = Vec::new();

    if let Some(cat) = category_covering_domain(domain, &active_cats) {
        if has_schedule {
            issues.push(Issue {
                code: "INEFFECTIVE_SCHEDULE",
                severity: "error",
                domain: domain.to_string(),
                message: format!(
                    "Category '{}' blocks '{}' 24/7. A schedule in the denylist has no effect.",
                    cat, domain
                ),
                suggestion: format!(
                    "Use allowlist instead: ndb allowlist add {} --schedule '...'",
                    domain
                ),
            });
        } else {
            issues.push(Issue {
                code: "REDUNDANT_DENYLIST",
                severity: "warning",
                domain: domain.to_string(),
                message: format!(
                    "'{}' is already blocked by NextDNS category '{}'",
                    domain, cat
                ),
                suggestion: "Adding to denylist is redundant".to_string(),
            });
        }
    }

    issues
}

/// Check congruency for a domain being added to the allowlist.
/// Returns warnings to include in the handler output.
pub fn check_allowlist_add(db: &Database, domain: &str) -> Vec<Issue> {
    let denylist = db
        .with_conn(|conn| crate::db::domains::list_blocked(conn, true))
        .unwrap_or_default();

    let denied: std::collections::HashSet<&str> =
        denylist.iter().map(|d| d.domain.as_str()).collect();

    let mut issues = Vec::new();

    // Check if siblings in the same service are blocked
    let siblings = siblings_in_service(domain);
    for sibling in &siblings {
        if denied.contains(sibling) {
            issues.push(Issue {
                code: "CONTRADICTORY_ALLOWLIST",
                severity: "warning",
                domain: domain.to_string(),
                message: format!(
                    "'{}' (same service as '{}') is in the denylist",
                    sibling, domain
                ),
                suggestion: format!(
                    "Remove '{}' from denylist for consistency, or don't allow '{}'",
                    sibling, domain
                ),
            });
        }
    }

    issues
}
