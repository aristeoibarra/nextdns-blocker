use secrecy::{ExposeSecret, SecretString};

use super::cache::TtlCache;
use super::circuit_breaker::CircuitBreaker;
use super::rate_limiter::RateLimiter;
use super::types::*;
use crate::error::AppError;

const BASE_URL: &str = "https://api.nextdns.io";

pub struct NextDnsClient {
    agent: ureq::Agent,
    api_key: String,
    profile_id: String,
    circuit_breaker: CircuitBreaker,
    rate_limiter: RateLimiter,
    denylist_cache: TtlCache<Vec<DenylistEntry>>,
    allowlist_cache: TtlCache<Vec<AllowlistEntry>>,
}

impl NextDnsClient {
    pub fn new(api_key: &SecretString, profile_id: String) -> Result<Self, AppError> {
        let agent = ureq::Agent::new_with_config(
            ureq::config::Config::builder()
                .timeout_global(Some(std::time::Duration::from_secs(30)))
                .build(),
        );

        Ok(Self {
            agent,
            api_key: api_key.expose_secret().to_string(),
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

    fn get_json<T: serde::de::DeserializeOwned>(&self, url: &str) -> ApiResult<T> {
        self.pre_request_check()?;

        let mut resp = self.agent.get(url)
            .header("Content-Type", "application/json")
            .header("X-Api-Key", &self.api_key)
            .call()
            .map_err(|e| {
                self.circuit_breaker.record_failure();
                map_ureq_error(e)
            })?;

        self.circuit_breaker.record_success();

        resp.body_mut().read_json::<T>().map_err(|e| AppError::General {
            message: format!("Failed to parse API response: {e}"),
            hint: None,
        })
    }

    fn post_json(&self, url: &str, body: &serde_json::Value) -> ApiResult<()> {
        self.pre_request_check()?;

        self.agent.post(url)
            .header("Content-Type", "application/json")
            .header("X-Api-Key", &self.api_key)
            .send_json(body)
            .map_err(|e| {
                self.circuit_breaker.record_failure();
                map_ureq_error(e)
            })?;

        self.circuit_breaker.record_success();
        Ok(())
    }

    fn put_json(&self, url: &str, body: &serde_json::Value) -> ApiResult<()> {
        self.pre_request_check()?;

        self.agent.put(url)
            .header("Content-Type", "application/json")
            .header("X-Api-Key", &self.api_key)
            .send_json(body)
            .map_err(|e| {
                self.circuit_breaker.record_failure();
                map_ureq_error(e)
            })?;

        self.circuit_breaker.record_success();
        Ok(())
    }

    fn delete(&self, url: &str) -> ApiResult<()> {
        self.pre_request_check()?;

        self.agent.delete(url)
            .header("Content-Type", "application/json")
            .header("X-Api-Key", &self.api_key)
            .call()
            .map_err(|e| {
                self.circuit_breaker.record_failure();
                map_ureq_error(e)
            })?;

        self.circuit_breaker.record_success();
        Ok(())
    }

    // === Denylist ===

    pub fn get_denylist(&self) -> ApiResult<Vec<DenylistEntry>> {
        if let Some(cached) = self.denylist_cache.get("denylist") {
            return Ok(cached);
        }

        let wrapper: ApiWrapper<DenylistEntry> = self.get_json(&self.endpoint("denylist"))?;
        self.denylist_cache.set("denylist".to_string(), wrapper.data.clone());
        Ok(wrapper.data)
    }

    pub fn add_to_denylist(&self, domain: &str) -> ApiResult<()> {
        let body = serde_json::json!({ "id": domain, "active": true });
        self.post_json(&self.endpoint("denylist"), &body)?;
        self.denylist_cache.invalidate("denylist");
        Ok(())
    }

    pub fn remove_from_denylist(&self, domain: &str) -> ApiResult<()> {
        self.delete(&format!("{}/{domain}", self.endpoint("denylist")))?;
        self.denylist_cache.invalidate("denylist");
        Ok(())
    }

    // === Allowlist ===

    pub fn get_allowlist(&self) -> ApiResult<Vec<AllowlistEntry>> {
        if let Some(cached) = self.allowlist_cache.get("allowlist") {
            return Ok(cached);
        }

        let wrapper: ApiWrapper<AllowlistEntry> = self.get_json(&self.endpoint("allowlist"))?;
        self.allowlist_cache.set("allowlist".to_string(), wrapper.data.clone());
        Ok(wrapper.data)
    }

    pub fn add_to_allowlist(&self, domain: &str) -> ApiResult<()> {
        let body = serde_json::json!({ "id": domain, "active": true });
        self.post_json(&self.endpoint("allowlist"), &body)?;
        self.allowlist_cache.invalidate("allowlist");
        Ok(())
    }

    pub fn remove_from_allowlist(&self, domain: &str) -> ApiResult<()> {
        self.delete(&format!("{}/{domain}", self.endpoint("allowlist")))?;
        self.allowlist_cache.invalidate("allowlist");
        Ok(())
    }

    // === Parental Control ===

    pub fn get_parental_categories(&self) -> ApiResult<Vec<ParentalCategory>> {
        let wrapper: ApiWrapper<ParentalCategory> = self.get_json(&self.endpoint("parentalControl/categories"))?;
        Ok(wrapper.data)
    }

    pub fn set_parental_category(&self, id: &str, active: bool) -> ApiResult<()> {
        let mut cats = self.get_parental_categories()?;
        if active {
            if !cats.iter().any(|c| c.id == id) {
                cats.push(ParentalCategory { id: id.to_string(), active: true, recreation: false });
            } else {
                for c in &mut cats {
                    if c.id == id { c.active = true; }
                }
            }
        } else {
            cats.retain(|c| c.id != id);
        }
        let body = serde_json::to_value(&cats).unwrap();
        self.put_json(&self.endpoint("parentalControl/categories"), &body)
    }

    pub fn get_parental_services(&self) -> ApiResult<Vec<ParentalService>> {
        let wrapper: ApiWrapper<ParentalService> = self.get_json(&self.endpoint("parentalControl/services"))?;
        Ok(wrapper.data)
    }

    pub fn set_parental_service(&self, id: &str, active: bool) -> ApiResult<()> {
        let mut svcs = self.get_parental_services()?;
        if active {
            if !svcs.iter().any(|s| s.id == id) {
                svcs.push(ParentalService { id: id.to_string(), active: true });
            } else {
                for s in &mut svcs {
                    if s.id == id { s.active = true; }
                }
            }
        } else {
            svcs.retain(|s| s.id != id);
        }
        let body = serde_json::to_value(&svcs).unwrap();
        self.put_json(&self.endpoint("parentalControl/services"), &body)
    }
}

fn map_ureq_error(e: ureq::Error) -> AppError {
    match e {
        ureq::Error::StatusCode(status) => AppError::Api {
            message: format!("API returned status {status}"),
            status_code: Some(status),
            hint: Some(match status {
                401 => "API key is invalid or expired. Check with `ndb config set-secret api_key`".to_string(),
                403 => "Access denied. Verify your API key and profile ID are correct".to_string(),
                404 => "Profile not found. Check your profile ID with `ndb config set-secret profile_id`".to_string(),
                429 => "Rate limited by NextDNS. Wait a moment and try again".to_string(),
                s if s >= 500 => "NextDNS server error. Try again later".to_string(),
                _ => format!("Unexpected HTTP status {status}"),
            }),
        },
        _ => AppError::General {
            message: format!("HTTP request failed: {e}"),
            hint: Some("Check network connectivity and try again".to_string()),
        },
    }
}
