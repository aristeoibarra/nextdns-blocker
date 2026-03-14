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

#[cfg(test)]
mod tests {
    use super::*;

    fn cache_with_ttl(ttl_ms: u64) -> TtlCache<String> {
        TtlCache {
            inner: RwLock::new(HashMap::new()),
            ttl: Duration::from_millis(ttl_ms),
        }
    }

    #[test]
    fn get_returns_none_for_missing_key() {
        let cache = TtlCache::<String>::new();
        assert!(cache.get("missing").is_none());
    }

    #[test]
    fn set_and_get() {
        let cache = TtlCache::new();
        cache.set("key".to_string(), "value".to_string());
        assert_eq!(cache.get("key"), Some("value".to_string()));
    }

    #[test]
    fn expired_entry_returns_none() {
        let cache = cache_with_ttl(1); // 1ms TTL
        cache.set("key".to_string(), "value".to_string());
        std::thread::sleep(Duration::from_millis(5));
        assert!(cache.get("key").is_none());
    }

    #[test]
    fn invalidate_removes_entry() {
        let cache = TtlCache::new();
        cache.set("key".to_string(), "value".to_string());
        cache.invalidate("key");
        assert!(cache.get("key").is_none());
    }

    #[test]
    fn expired_entries_are_cleaned_on_get() {
        let cache = cache_with_ttl(1);
        cache.set("a".to_string(), "1".to_string());
        cache.set("b".to_string(), "2".to_string());
        std::thread::sleep(Duration::from_millis(5));

        // Trigger cleanup by reading a missing key
        cache.get("a");

        // Internal map should have been cleaned
        let inner = cache.inner.read().unwrap();
        assert!(inner.is_empty());
    }
}
