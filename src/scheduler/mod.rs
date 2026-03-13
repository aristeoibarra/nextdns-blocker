pub mod types;

use chrono::{Datelike, NaiveTime, Timelike, Weekday};

use types::{DaySchedule, Schedule, TimeRange};

/// Trait for abstracting time (for testing).
pub trait Clock: Send + Sync {
    fn now(&self) -> chrono::DateTime<chrono::Utc>;
    fn now_in_tz(&self, tz: &chrono_tz::Tz) -> chrono::DateTime<chrono_tz::Tz>;
}

/// Real system clock.
pub struct SystemClock;

impl Clock for SystemClock {
    fn now(&self) -> chrono::DateTime<chrono::Utc> {
        chrono::Utc::now()
    }

    fn now_in_tz(&self, tz: &chrono_tz::Tz) -> chrono::DateTime<chrono_tz::Tz> {
        chrono::Utc::now().with_timezone(tz)
    }
}

pub struct ScheduleEvaluator {
    clock: Box<dyn Clock>,
    timezone: chrono_tz::Tz,
}

impl ScheduleEvaluator {
    pub fn new(timezone: chrono_tz::Tz) -> Self {
        Self {
            clock: Box::new(SystemClock),
            timezone,
        }
    }

    pub fn with_clock(clock: Box<dyn Clock>, timezone: chrono_tz::Tz) -> Self {
        Self { clock, timezone }
    }

    /// Check if the current time falls within the schedule's available hours.
    /// Returns true if the item should be AVAILABLE (unblocked).
    /// If schedule is None, the item is always blocked (never available).
    pub fn is_available(&self, schedule: Option<&Schedule>) -> bool {
        let Some(schedule) = schedule else {
            return false;
        };

        let now = self.clock.now_in_tz(&self.timezone);
        let weekday = now.weekday();
        let current_time = NaiveTime::from_hms_opt(
            now.hour(),
            now.minute(),
            now.second(),
        )
        .expect("valid time from DateTime");

        for block in &schedule.available_hours {
            if !block.days.contains(&weekday) {
                continue;
            }
            for range in &block.time_ranges {
                if is_time_in_range(current_time, range) {
                    return true;
                }
            }
        }

        false
    }

    /// Check if the item should be blocked right now.
    pub fn should_block(&self, schedule: Option<&Schedule>) -> bool {
        !self.is_available(schedule)
    }
}

/// Check if a time falls within a range, supporting overnight ranges (e.g., 22:00-02:00).
fn is_time_in_range(time: NaiveTime, range: &TimeRange) -> bool {
    if range.start <= range.end {
        // Normal range (e.g., 09:00-17:00)
        time >= range.start && time < range.end
    } else {
        // Overnight range (e.g., 22:00-02:00)
        time >= range.start || time < range.end
    }
}

fn parse_weekday(s: &str) -> Option<Weekday> {
    match s.to_lowercase().as_str() {
        "monday" | "mon" => Some(Weekday::Mon),
        "tuesday" | "tue" => Some(Weekday::Tue),
        "wednesday" | "wed" => Some(Weekday::Wed),
        "thursday" | "thu" => Some(Weekday::Thu),
        "friday" | "fri" => Some(Weekday::Fri),
        "saturday" | "sat" => Some(Weekday::Sat),
        "sunday" | "sun" => Some(Weekday::Sun),
        _ => None,
    }
}

/// Validate a config Schedule, returning an error message if any fields are invalid.
/// Use this at creation time (handlers) to reject bad schedules before they reach the DB.
pub fn validate_config_schedule(
    config_schedule: &crate::config::types::Schedule,
) -> Result<(), String> {
    for (i, block) in config_schedule.available_hours.iter().enumerate() {
        for day in &block.days {
            if parse_weekday(day).is_none() {
                return Err(format!("Invalid day '{}' in block {}", day, i));
            }
        }
        for range in &block.time_ranges {
            if NaiveTime::parse_from_str(&range.start, "%H:%M").is_err() {
                return Err(format!("Invalid start time '{}' in block {}", range.start, i));
            }
            if NaiveTime::parse_from_str(&range.end, "%H:%M").is_err() {
                return Err(format!("Invalid end time '{}' in block {}", range.end, i));
            }
        }
    }
    Ok(())
}

/// Parse a config Schedule into the evaluator's Schedule type.
/// Invalid days and time ranges are skipped (use `validate_config_schedule` first
/// to catch errors at creation time).
pub fn parse_config_schedule(
    config_schedule: &crate::config::types::Schedule,
) -> Option<Schedule> {
    let mut available_hours = Vec::new();

    for block in &config_schedule.available_hours {
        let days: Vec<Weekday> = block
            .days
            .iter()
            .filter_map(|d| parse_weekday(d))
            .collect();

        let time_ranges: Vec<TimeRange> = block
            .time_ranges
            .iter()
            .filter_map(|r| {
                let start = NaiveTime::parse_from_str(&r.start, "%H:%M").ok()?;
                let end = NaiveTime::parse_from_str(&r.end, "%H:%M").ok()?;
                Some(TimeRange { start, end })
            })
            .collect();

        if !days.is_empty() && !time_ranges.is_empty() {
            available_hours.push(DaySchedule { days, time_ranges });
        }
    }

    if available_hours.is_empty() {
        None
    } else {
        Some(Schedule { available_hours })
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    struct FixedClock(chrono::DateTime<chrono::Utc>);

    impl Clock for FixedClock {
        fn now(&self) -> chrono::DateTime<chrono::Utc> {
            self.0
        }
        fn now_in_tz(&self, tz: &chrono_tz::Tz) -> chrono::DateTime<chrono_tz::Tz> {
            self.0.with_timezone(tz)
        }
    }

    fn make_schedule(days: Vec<Weekday>, start: &str, end: &str) -> Schedule {
        Schedule {
            available_hours: vec![DaySchedule {
                days,
                time_ranges: vec![TimeRange {
                    start: NaiveTime::parse_from_str(start, "%H:%M").unwrap(),
                    end: NaiveTime::parse_from_str(end, "%H:%M").unwrap(),
                }],
            }],
        }
    }

    #[test]
    fn available_during_schedule() {
        // Monday 14:00 UTC
        let dt = chrono::DateTime::parse_from_rfc3339("2026-03-02T14:00:00Z")
            .unwrap()
            .to_utc();
        let clock = Box::new(FixedClock(dt));
        let eval = ScheduleEvaluator::with_clock(clock, chrono_tz::UTC);

        let sched = make_schedule(vec![Weekday::Mon], "12:00", "18:00");
        assert!(eval.is_available(Some(&sched)));
    }

    #[test]
    fn blocked_outside_schedule() {
        // Monday 08:00 UTC
        let dt = chrono::DateTime::parse_from_rfc3339("2026-03-02T08:00:00Z")
            .unwrap()
            .to_utc();
        let clock = Box::new(FixedClock(dt));
        let eval = ScheduleEvaluator::with_clock(clock, chrono_tz::UTC);

        let sched = make_schedule(vec![Weekday::Mon], "12:00", "18:00");
        assert!(!eval.is_available(Some(&sched)));
    }

    #[test]
    fn no_schedule_always_blocked() {
        let dt = chrono::DateTime::parse_from_rfc3339("2026-03-02T14:00:00Z")
            .unwrap()
            .to_utc();
        let clock = Box::new(FixedClock(dt));
        let eval = ScheduleEvaluator::with_clock(clock, chrono_tz::UTC);
        assert!(!eval.is_available(None));
    }

    #[test]
    fn overnight_range() {
        // Monday 23:30 UTC
        let dt = chrono::DateTime::parse_from_rfc3339("2026-03-02T23:30:00Z")
            .unwrap()
            .to_utc();
        let clock = Box::new(FixedClock(dt));
        let eval = ScheduleEvaluator::with_clock(clock, chrono_tz::UTC);

        let sched = make_schedule(vec![Weekday::Mon], "22:00", "02:00");
        assert!(eval.is_available(Some(&sched)));
    }

    #[test]
    fn validate_rejects_invalid_time() {
        let sched = crate::config::types::Schedule {
            available_hours: vec![crate::config::types::AvailableHoursBlock {
                days: vec!["mon".to_string()],
                time_ranges: vec![crate::config::types::TimeRange {
                    start: "25:00".to_string(),
                    end: "18:00".to_string(),
                }],
            }],
        };
        assert!(validate_config_schedule(&sched).is_err());
    }

    #[test]
    fn validate_rejects_invalid_day() {
        let sched = crate::config::types::Schedule {
            available_hours: vec![crate::config::types::AvailableHoursBlock {
                days: vec!["funday".to_string()],
                time_ranges: vec![crate::config::types::TimeRange {
                    start: "09:00".to_string(),
                    end: "17:00".to_string(),
                }],
            }],
        };
        assert!(validate_config_schedule(&sched).is_err());
    }

    #[test]
    fn validate_accepts_valid_schedule() {
        let sched = crate::config::types::Schedule {
            available_hours: vec![crate::config::types::AvailableHoursBlock {
                days: vec!["mon".to_string(), "fri".to_string()],
                time_ranges: vec![crate::config::types::TimeRange {
                    start: "09:00".to_string(),
                    end: "17:00".to_string(),
                }],
            }],
        };
        assert!(validate_config_schedule(&sched).is_ok());
    }
}
