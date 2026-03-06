use crate::error::{AppError, ValidationDetail};
use crate::types::Domain;

use super::types::AppConfig;

/// Validate an entire AppConfig, returning all validation errors.
pub fn validate_config(config: &AppConfig) -> Result<(), AppError> {
    let mut details = Vec::new();

    // Validate timezone if set
    if let Some(ref tz) = config.settings.timezone {
        if tz.parse::<chrono_tz::Tz>().is_err() {
            details.push(ValidationDetail {
                field: "settings.timezone".to_string(),
                reason: format!("Invalid timezone: {tz}"),
            });
        }
    }

    // Validate blocklist domains
    for (i, entry) in config.blocklist.iter().enumerate() {
        if Domain::new(&entry.domain).is_err() {
            details.push(ValidationDetail {
                field: format!("blocklist[{i}].domain"),
                reason: format!("Invalid domain: {}", entry.domain),
            });
        }
        if let Some(ref sched) = entry.schedule {
            validate_schedule(sched, &format!("blocklist[{i}].schedule"), &mut details);
        }
        validate_unblock_delay(&entry.unblock_delay, &format!("blocklist[{i}].unblock_delay"), &mut details);
    }

    // Validate allowlist domains
    for (i, entry) in config.allowlist.iter().enumerate() {
        if Domain::new(&entry.domain).is_err() {
            details.push(ValidationDetail {
                field: format!("allowlist[{i}].domain"),
                reason: format!("Invalid domain: {}", entry.domain),
            });
        }
    }

    // Validate categories
    for (i, cat) in config.categories.iter().enumerate() {
        for (j, domain) in cat.domains.iter().enumerate() {
            if Domain::new(domain).is_err() {
                details.push(ValidationDetail {
                    field: format!("categories[{i}].domains[{j}]"),
                    reason: format!("Invalid domain: {domain}"),
                });
            }
        }
        if let Some(ref sched) = cat.schedule {
            validate_schedule(sched, &format!("categories[{i}].schedule"), &mut details);
        }
        validate_unblock_delay(&cat.unblock_delay, &format!("categories[{i}].unblock_delay"), &mut details);
    }

    // Validate NextDNS categories
    for (i, cat) in config.nextdns.categories.iter().enumerate() {
        if cat.id.is_empty() {
            details.push(ValidationDetail {
                field: format!("nextdns.categories[{i}].id"),
                reason: "Category ID cannot be empty".to_string(),
            });
        }
    }

    // Validate NextDNS services
    for (i, svc) in config.nextdns.services.iter().enumerate() {
        if svc.id.is_empty() {
            details.push(ValidationDetail {
                field: format!("nextdns.services[{i}].id"),
                reason: "Service ID cannot be empty".to_string(),
            });
        }
    }

    if details.is_empty() {
        Ok(())
    } else {
        Err(AppError::Validation {
            message: format!("Configuration has {} validation error(s)", details.len()),
            details,
            hint: Some("Fix the listed errors in your config.json".to_string()),
        })
    }
}

fn validate_schedule(
    schedule: &super::types::Schedule,
    path: &str,
    details: &mut Vec<ValidationDetail>,
) {
    let valid_days = [
        "monday",
        "tuesday",
        "wednesday",
        "thursday",
        "friday",
        "saturday",
        "sunday",
    ];

    for (i, block) in schedule.available_hours.iter().enumerate() {
        for day in &block.days {
            if !valid_days.contains(&day.to_lowercase().as_str()) {
                details.push(ValidationDetail {
                    field: format!("{path}.available_hours[{i}].days"),
                    reason: format!("Invalid day: {day}"),
                });
            }
        }
        for (j, range) in block.time_ranges.iter().enumerate() {
            if parse_time(&range.start).is_none() {
                details.push(ValidationDetail {
                    field: format!("{path}.available_hours[{i}].time_ranges[{j}].start"),
                    reason: format!("Invalid time format: {}", range.start),
                });
            }
            if parse_time(&range.end).is_none() {
                details.push(ValidationDetail {
                    field: format!("{path}.available_hours[{i}].time_ranges[{j}].end"),
                    reason: format!("Invalid time format: {}", range.end),
                });
            }
        }
    }
}

fn validate_unblock_delay(delay: &str, path: &str, details: &mut Vec<ValidationDetail>) {
    if delay == "never" || delay == "0" {
        return;
    }
    if humantime::parse_duration(delay).is_err() {
        details.push(ValidationDetail {
            field: path.to_string(),
            reason: format!("Invalid unblock_delay: {delay}. Use '0', 'never', or a duration like '4h'"),
        });
    }
}

/// Parse HH:MM time string.
fn parse_time(s: &str) -> Option<chrono::NaiveTime> {
    chrono::NaiveTime::parse_from_str(s, "%H:%M").ok()
}
