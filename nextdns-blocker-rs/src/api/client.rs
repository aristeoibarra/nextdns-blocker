use std::time::Duration;

use reqwest::header::{HeaderMap, HeaderValue, CONTENT_TYPE};
use secrecy::{ExposeSecret, SecretString};

use super::cache::TtlCache;
use super::circuit_breaker::CircuitBreaker;
use super::rate_limiter::RateLimiter;
use super::types::*;
use crate::error::AppError;

const BASE_URL: &str = "https://api.nextdns.io";

pub struct NextDnsClient {
    http: reqwest::Client,
    profile_id: String,
    circuit_breaker: CircuitBreaker,
    rate_limiter: RateLimiter,
    denylist_cache: TtlCache<Vec<DenylistEntry>>,
    allowlist_cache: TtlCache<Vec<AllowlistEntry>>,
}

impl NextDnsClient {
    pub fn new(api_key: &SecretString, profile_id: String) -> Result<Self, AppError> {
        let mut headers = HeaderMap::new();
        headers.insert(CONTENT_TYPE, HeaderValue::from_static("application/json"));
        headers.insert(
            "X-Api-Key",
            HeaderValue::from_str(api_key.expose_secret()).map_err(|e| AppError::Config {
                message: format!("Invalid API key format: {e}"),
                hint: None,
            })?,
        );

        let http = reqwest::Client::builder()
            .default_headers(headers)
            .timeout(Duration::from_secs(30))
            .connect_timeout(Duration::from_secs(10))
            .build()?;

        Ok(Self {
            http,
            profile_id,
            circuit_breaker: CircuitBreaker::new(),
            rate_limiter: RateLimiter::new(),
            denylist_cache: TtlCache::new(),
            allowlist_cache: TtlCache::new(),
        })
    }

    fn endpoint(&self, path: &str) -> String {
        format!("{BASE_URL}/profiles/{}/{path}", self.profile_id)
    }

    /// Check circuit breaker and rate limiter before making a request.
    fn pre_request_check(&self) -> Result<(), AppError> {
        if !self.circuit_breaker.allow_request() {
            return Err(AppError::Api {
                message: "Circuit breaker is open - too many recent failures".to_string(),
                status_code: None,
                hint: Some("Wait a moment and try again, or check `ndb status`".to_string()),
            });
        }

        if !self.rate_limiter.try_acquire() {
            return Err(AppError::Api {
                message: "Rate limit exceeded".to_string(),
                status_code: Some(429),
                hint: Some("Wait before making more API requests".to_string()),
            });
        }

        Ok(())
    }

    // === Denylist ===

    pub async fn get_denylist(&self) -> ApiResult<Vec<DenylistEntry>> {
        if let Some(cached) = self.denylist_cache.get("denylist").await {
            return Ok(cached);
        }

        self.pre_request_check()?;

        let resp = self
            .http
            .get(self.endpoint("denylist"))
            .send()
            .await
            .map_err(|e| {
                self.circuit_breaker.record_failure();
                AppError::Http { source: e }
            })?;

        self.circuit_breaker.record_success();

        if !resp.status().is_success() {
            return Err(AppError::Api {
                message: format!("API returned status {}", resp.status()),
                status_code: Some(resp.status().as_u16()),
                hint: Some("Check your API key and profile ID".to_string()),
            });
        }

        let entries: Vec<DenylistEntry> = resp.json().await?;
        self.denylist_cache
            .set("denylist".to_string(), entries.clone())
            .await;
        Ok(entries)
    }

    pub async fn add_to_denylist(&self, domain: &str) -> ApiResult<()> {
        self.pre_request_check()?;

        let body = serde_json::json!({ "id": domain, "active": true });
        let resp = self
            .http
            .put(self.endpoint("denylist"))
            .json(&body)
            .send()
            .await
            .map_err(|e| {
                self.circuit_breaker.record_failure();
                AppError::Http { source: e }
            })?;

        self.circuit_breaker.record_success();
        self.denylist_cache.invalidate("denylist").await;

        if !resp.status().is_success() {
            return Err(AppError::Api {
                message: format!("Failed to add domain to denylist: {}", resp.status()),
                status_code: Some(resp.status().as_u16()),
                hint: None,
            });
        }

        Ok(())
    }

    pub async fn remove_from_denylist(&self, domain: &str) -> ApiResult<()> {
        self.pre_request_check()?;

        let resp = self
            .http
            .delete(format!("{}/{domain}", self.endpoint("denylist")))
            .send()
            .await
            .map_err(|e| {
                self.circuit_breaker.record_failure();
                AppError::Http { source: e }
            })?;

        self.circuit_breaker.record_success();
        self.denylist_cache.invalidate("denylist").await;

        if !resp.status().is_success() {
            return Err(AppError::Api {
                message: format!("Failed to remove domain from denylist: {}", resp.status()),
                status_code: Some(resp.status().as_u16()),
                hint: None,
            });
        }

        Ok(())
    }

    // === Allowlist ===

    pub async fn get_allowlist(&self) -> ApiResult<Vec<AllowlistEntry>> {
        if let Some(cached) = self.allowlist_cache.get("allowlist").await {
            return Ok(cached);
        }

        self.pre_request_check()?;

        let resp = self
            .http
            .get(self.endpoint("allowlist"))
            .send()
            .await
            .map_err(|e| {
                self.circuit_breaker.record_failure();
                AppError::Http { source: e }
            })?;

        self.circuit_breaker.record_success();

        if !resp.status().is_success() {
            return Err(AppError::Api {
                message: format!("API returned status {}", resp.status()),
                status_code: Some(resp.status().as_u16()),
                hint: Some("Check your API key and profile ID".to_string()),
            });
        }

        let entries: Vec<AllowlistEntry> = resp.json().await?;
        self.allowlist_cache
            .set("allowlist".to_string(), entries.clone())
            .await;
        Ok(entries)
    }

    pub async fn add_to_allowlist(&self, domain: &str) -> ApiResult<()> {
        self.pre_request_check()?;

        let body = serde_json::json!({ "id": domain, "active": true });
        let resp = self
            .http
            .put(self.endpoint("allowlist"))
            .json(&body)
            .send()
            .await
            .map_err(|e| {
                self.circuit_breaker.record_failure();
                AppError::Http { source: e }
            })?;

        self.circuit_breaker.record_success();
        self.allowlist_cache.invalidate("allowlist").await;

        if !resp.status().is_success() {
            return Err(AppError::Api {
                message: format!("Failed to add domain to allowlist: {}", resp.status()),
                status_code: Some(resp.status().as_u16()),
                hint: None,
            });
        }

        Ok(())
    }

    pub async fn remove_from_allowlist(&self, domain: &str) -> ApiResult<()> {
        self.pre_request_check()?;

        let resp = self
            .http
            .delete(format!("{}/{domain}", self.endpoint("allowlist")))
            .send()
            .await
            .map_err(|e| {
                self.circuit_breaker.record_failure();
                AppError::Http { source: e }
            })?;

        self.circuit_breaker.record_success();
        self.allowlist_cache.invalidate("allowlist").await;

        if !resp.status().is_success() {
            return Err(AppError::Api {
                message: format!("Failed to remove domain from allowlist: {}", resp.status()),
                status_code: Some(resp.status().as_u16()),
                hint: None,
            });
        }

        Ok(())
    }

    // === Parental Control ===

    pub async fn get_parental_categories(&self) -> ApiResult<Vec<ParentalCategory>> {
        self.pre_request_check()?;

        let resp = self
            .http
            .get(self.endpoint("parentalControl/categories"))
            .send()
            .await
            .map_err(|e| {
                self.circuit_breaker.record_failure();
                AppError::Http { source: e }
            })?;

        self.circuit_breaker.record_success();

        if !resp.status().is_success() {
            return Err(AppError::Api {
                message: format!("API returned status {}", resp.status()),
                status_code: Some(resp.status().as_u16()),
                hint: None,
            });
        }

        resp.json().await.map_err(AppError::from)
    }

    pub async fn set_parental_category(&self, id: &str, active: bool) -> ApiResult<()> {
        self.pre_request_check()?;

        let body = serde_json::json!({ "id": id, "active": active });
        let resp = self
            .http
            .put(self.endpoint("parentalControl/categories"))
            .json(&body)
            .send()
            .await
            .map_err(|e| {
                self.circuit_breaker.record_failure();
                AppError::Http { source: e }
            })?;

        self.circuit_breaker.record_success();

        if !resp.status().is_success() {
            return Err(AppError::Api {
                message: format!("Failed to set parental category: {}", resp.status()),
                status_code: Some(resp.status().as_u16()),
                hint: None,
            });
        }

        Ok(())
    }

    pub async fn get_parental_services(&self) -> ApiResult<Vec<ParentalService>> {
        self.pre_request_check()?;

        let resp = self
            .http
            .get(self.endpoint("parentalControl/services"))
            .send()
            .await
            .map_err(|e| {
                self.circuit_breaker.record_failure();
                AppError::Http { source: e }
            })?;

        self.circuit_breaker.record_success();

        if !resp.status().is_success() {
            return Err(AppError::Api {
                message: format!("API returned status {}", resp.status()),
                status_code: Some(resp.status().as_u16()),
                hint: None,
            });
        }

        resp.json().await.map_err(AppError::from)
    }

    pub async fn set_parental_service(&self, id: &str, active: bool) -> ApiResult<()> {
        self.pre_request_check()?;

        let body = serde_json::json!({ "id": id, "active": active });
        let resp = self
            .http
            .put(self.endpoint("parentalControl/services"))
            .json(&body)
            .send()
            .await
            .map_err(|e| {
                self.circuit_breaker.record_failure();
                AppError::Http { source: e }
            })?;

        self.circuit_breaker.record_success();

        if !resp.status().is_success() {
            return Err(AppError::Api {
                message: format!("Failed to set parental service: {}", resp.status()),
                status_code: Some(resp.status().as_u16()),
                hint: None,
            });
        }

        Ok(())
    }
}
