use std::collections::HashMap;
use std::time::{Duration, Instant};

use tokio::sync::RwLock;

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

    pub fn with_ttl(ttl: Duration) -> Self {
        Self {
            inner: RwLock::new(HashMap::new()),
            ttl,
        }
    }

    pub async fn get(&self, key: &str) -> Option<V> {
        let cache = self.inner.read().await;
        cache.get(key).and_then(|entry| {
            if entry.inserted_at.elapsed() < self.ttl {
                Some(entry.value.clone())
            } else {
                None
            }
        })
    }

    pub async fn set(&self, key: String, value: V) {
        let mut cache = self.inner.write().await;
        cache.insert(
            key,
            CacheEntry {
                value,
                inserted_at: Instant::now(),
            },
        );
    }

    pub async fn invalidate(&self, key: &str) {
        let mut cache = self.inner.write().await;
        cache.remove(key);
    }

    pub async fn clear(&self) {
        let mut cache = self.inner.write().await;
        cache.clear();
    }
}

impl<V: Clone> Default for TtlCache<V> {
    fn default() -> Self {
        Self::new()
    }
}
