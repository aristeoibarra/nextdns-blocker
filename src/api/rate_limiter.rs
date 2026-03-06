use std::collections::VecDeque;
use std::sync::Mutex;
use std::time::{Duration, Instant};

use crate::config::constants::{DEFAULT_RATE_LIMIT_REQUESTS, DEFAULT_RATE_LIMIT_WINDOW_SECS};

/// Sliding window rate limiter.
pub struct RateLimiter {
    inner: Mutex<Inner>,
}

struct Inner {
    window: Duration,
    max_requests: u32,
    timestamps: VecDeque<Instant>,
}

impl RateLimiter {
    pub fn new() -> Self {
        Self {
            inner: Mutex::new(Inner {
                window: Duration::from_secs(DEFAULT_RATE_LIMIT_WINDOW_SECS),
                max_requests: DEFAULT_RATE_LIMIT_REQUESTS,
                timestamps: VecDeque::new(),
            }),
        }
    }

    pub fn with_config(max_requests: u32, window: Duration) -> Self {
        Self {
            inner: Mutex::new(Inner {
                window,
                max_requests,
                timestamps: VecDeque::new(),
            }),
        }
    }

    /// Check if a request is allowed. If yes, records it.
    /// On poisoned mutex, defaults to rejecting (fail-safe).
    pub fn try_acquire(&self) -> bool {
        let Ok(mut inner) = self.inner.lock() else {
            return false;
        };
        let now = Instant::now();
        let cutoff = now - inner.window;

        // Remove expired timestamps
        while inner
            .timestamps
            .front()
            .is_some_and(|&ts| ts < cutoff)
        {
            inner.timestamps.pop_front();
        }

        if inner.timestamps.len() < inner.max_requests as usize {
            inner.timestamps.push_back(now);
            true
        } else {
            false
        }
    }

    /// Time until next request is allowed.
    pub fn wait_duration(&self) -> Option<Duration> {
        let Ok(inner) = self.inner.lock() else {
            return Some(Duration::from_secs(1));
        };
        let now = Instant::now();

        if inner.timestamps.len() < inner.max_requests as usize {
            return None;
        }

        inner
            .timestamps
            .front()
            .map(|&oldest| {
                let expires = oldest + inner.window;
                if expires > now {
                    expires - now
                } else {
                    Duration::ZERO
                }
            })
    }
}

impl Default for RateLimiter {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn allows_within_limit() {
        let rl = RateLimiter::with_config(3, Duration::from_secs(60));
        assert!(rl.try_acquire());
        assert!(rl.try_acquire());
        assert!(rl.try_acquire());
        assert!(!rl.try_acquire());
    }

    #[test]
    fn no_wait_when_available() {
        let rl = RateLimiter::with_config(3, Duration::from_secs(60));
        assert!(rl.wait_duration().is_none());
    }
}
