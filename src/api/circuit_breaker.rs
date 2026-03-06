use std::sync::Mutex;
use std::time::{Duration, Instant};

use crate::config::constants::{DEFAULT_CB_FAILURE_THRESHOLD, DEFAULT_CB_RESET_TIMEOUT_SECS};

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum State {
    Closed,
    Open,
    HalfOpen,
}

pub struct CircuitBreaker {
    inner: Mutex<Inner>,
}

struct Inner {
    state: State,
    failure_count: u32,
    last_failure: Option<Instant>,
    threshold: u32,
    reset_timeout: Duration,
}

impl CircuitBreaker {
    pub fn new() -> Self {
        Self {
            inner: Mutex::new(Inner {
                state: State::Closed,
                failure_count: 0,
                last_failure: None,
                threshold: DEFAULT_CB_FAILURE_THRESHOLD,
                reset_timeout: Duration::from_secs(DEFAULT_CB_RESET_TIMEOUT_SECS),
            }),
        }
    }

    pub fn with_config(threshold: u32, reset_timeout: Duration) -> Self {
        Self {
            inner: Mutex::new(Inner {
                state: State::Closed,
                failure_count: 0,
                last_failure: None,
                threshold,
                reset_timeout,
            }),
        }
    }

    /// Check if requests are allowed.
    /// On poisoned mutex, defaults to blocking (fail-safe).
    pub fn allow_request(&self) -> bool {
        let Ok(mut inner) = self.inner.lock() else {
            return false;
        };
        match inner.state {
            State::Closed => true,
            State::Open => {
                if let Some(last) = inner.last_failure {
                    if last.elapsed() >= inner.reset_timeout {
                        inner.state = State::HalfOpen;
                        true
                    } else {
                        false
                    }
                } else {
                    true
                }
            }
            State::HalfOpen => true,
        }
    }

    /// Record a successful request.
    pub fn record_success(&self) {
        if let Ok(mut inner) = self.inner.lock() {
            inner.failure_count = 0;
            inner.state = State::Closed;
        }
    }

    /// Record a failed request.
    pub fn record_failure(&self) {
        if let Ok(mut inner) = self.inner.lock() {
            inner.failure_count += 1;
            inner.last_failure = Some(Instant::now());
            if inner.failure_count >= inner.threshold {
                inner.state = State::Open;
            }
        }
    }

    pub fn state(&self) -> State {
        self.inner
            .lock()
            .map(|inner| inner.state)
            .unwrap_or(State::Open)
    }

    pub fn failure_count(&self) -> u32 {
        self.inner
            .lock()
            .map(|inner| inner.failure_count)
            .unwrap_or(0)
    }
}

impl Default for CircuitBreaker {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn starts_closed() {
        let cb = CircuitBreaker::new();
        assert_eq!(cb.state(), State::Closed);
        assert!(cb.allow_request());
    }

    #[test]
    fn opens_after_threshold() {
        let cb = CircuitBreaker::with_config(3, Duration::from_secs(60));
        cb.record_failure();
        cb.record_failure();
        assert_eq!(cb.state(), State::Closed);
        cb.record_failure();
        assert_eq!(cb.state(), State::Open);
        assert!(!cb.allow_request());
    }

    #[test]
    fn resets_on_success() {
        let cb = CircuitBreaker::with_config(3, Duration::from_secs(60));
        cb.record_failure();
        cb.record_failure();
        cb.record_success();
        assert_eq!(cb.failure_count(), 0);
        assert_eq!(cb.state(), State::Closed);
    }
}
