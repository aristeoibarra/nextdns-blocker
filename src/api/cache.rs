use std::collections::HashMap;
use std::sync::RwLock;
use std::time::{Duration, Instant};

use crate::config::constants::DEFAULT_CACHE_TTL_SECS;

/// In-memory TTL cache.
pub struct TtlCache<V> {
    inner: RwLock<HashMap<String, CacheEntry<V>>>,
    ttl: Duration,
}

struct CacheEntry<V> {
    value: V,
    inserted_at: Instant,
}

impl<V: Clone> TtlCache<V> {
    pub fn new() -> Self {
        Self {
            inner: RwLock::new(HashMap::new()),
            ttl: Duration::from_secs(DEFAULT_CACHE_TTL_SECS),
        }
    }

    pub fn get(&self, key: &str) -> Option<V> {
        // Try read-only first for the fast path
        {
            let cache = self.inner.read().unwrap_or_else(|e| e.into_inner());
            if let Some(entry) = cache.get(key) {
                if entry.inserted_at.elapsed() < self.ttl {
                    return Some(entry.value.clone());
                }
            }
        }
        // Entry is expired or missing — acquire write lock to evict expired entries
        if let Ok(mut cache) = self.inner.write() {
            cache.retain(|_, entry| entry.inserted_at.elapsed() < self.ttl);
        }
        None
    }

    pub fn set(&self, key: String, value: V) {
        if let Ok(mut cache) = self.inner.write() {
            cache.insert(key, CacheEntry { value, inserted_at: Instant::now() });
        }
    }

    pub fn invalidate(&self, key: &str) {
        if let Ok(mut cache) = self.inner.write() {
            cache.remove(key);
        }
    }
}

impl<V: Clone> Default for TtlCache<V> {
    fn default() -> Self {
        Self::new()
    }
}
