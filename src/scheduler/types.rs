use chrono::{NaiveTime, Weekday};

/// Parsed schedule ready for evaluation.
#[derive(Debug, Clone)]
pub struct Schedule {
    pub available_hours: Vec<DaySchedule>,
}

/// A group of days with their time ranges.
#[derive(Debug, Clone)]
pub struct DaySchedule {
    pub days: Vec<Weekday>,
    pub time_ranges: Vec<TimeRange>,
}

/// A time range within a day.
#[derive(Debug, Clone)]
pub struct TimeRange {
    pub start: NaiveTime,
    pub end: NaiveTime,
}
