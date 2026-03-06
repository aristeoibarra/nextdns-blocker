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
        let cache = self.inner.read().unwrap_or_else(|e| e.into_inner());
        cache.get(key).and_then(|entry| {
            if entry.inserted_at.elapsed() < self.ttl {
                Some(entry.value.clone())
            } else {
                None
            }
        })
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
