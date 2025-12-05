"""Tests for remote domains caching functionality."""

import json
import time
from unittest.mock import patch

import pytest
import requests as req
import responses

from nextdns_blocker.config import (
    fetch_remote_domains,
    get_cache_status,
    get_cached_domains,
    load_domains,
    save_domains_cache,
)
from nextdns_blocker.exceptions import ConfigurationError


class TestGetCachedDomains:
    """Tests for get_cached_domains function."""

    def test_returns_none_when_no_cache(self, tmp_path):
        """Should return None when cache file doesn't exist."""
        with patch(
            "nextdns_blocker.config.get_domains_cache_file",
            return_value=tmp_path / "nonexistent.json",
        ):
            result = get_cached_domains()
            assert result is None

    def test_returns_cached_data_when_valid(self, tmp_path):
        """Should return cached data when cache is valid."""
        cache_file = tmp_path / "domains_cache.json"
        cache_data = {"timestamp": time.time(), "data": {"domains": [{"domain": "example.com"}]}}
        cache_file.write_text(json.dumps(cache_data))

        with patch("nextdns_blocker.config.get_domains_cache_file", return_value=cache_file):
            result = get_cached_domains()
            assert result == {"domains": [{"domain": "example.com"}]}

    def test_returns_none_when_expired(self, tmp_path):
        """Should return None when cache is expired."""
        cache_file = tmp_path / "domains_cache.json"
        # Set timestamp to 2 hours ago (beyond 1 hour TTL)
        cache_data = {
            "timestamp": time.time() - 7200,
            "data": {"domains": [{"domain": "example.com"}]},
        }
        cache_file.write_text(json.dumps(cache_data))

        with patch("nextdns_blocker.config.get_domains_cache_file", return_value=cache_file):
            result = get_cached_domains()
            assert result is None

    def test_custom_max_age(self, tmp_path):
        """Should respect custom max_age parameter."""
        cache_file = tmp_path / "domains_cache.json"
        # Set timestamp to 30 seconds ago
        cache_data = {
            "timestamp": time.time() - 30,
            "data": {"domains": [{"domain": "example.com"}]},
        }
        cache_file.write_text(json.dumps(cache_data))

        with patch("nextdns_blocker.config.get_domains_cache_file", return_value=cache_file):
            # With 60 second max_age, should return data
            result = get_cached_domains(max_age=60)
            assert result is not None

            # With 10 second max_age, should return None
            result = get_cached_domains(max_age=10)
            assert result is None

    def test_handles_corrupted_cache(self, tmp_path):
        """Should return None for corrupted cache file."""
        cache_file = tmp_path / "domains_cache.json"
        cache_file.write_text("not valid json")

        with patch("nextdns_blocker.config.get_domains_cache_file", return_value=cache_file):
            result = get_cached_domains()
            assert result is None


class TestSaveDomainsCache:
    """Tests for save_domains_cache function."""

    def test_creates_cache_file(self, tmp_path):
        """Should create cache file with correct content."""
        cache_file = tmp_path / "cache" / "domains_cache.json"

        with patch("nextdns_blocker.config.get_domains_cache_file", return_value=cache_file):
            data = {"domains": [{"domain": "example.com"}]}
            result = save_domains_cache(data)

            assert result is True
            assert cache_file.exists()

            saved = json.loads(cache_file.read_text())
            assert "timestamp" in saved
            assert saved["data"] == data

    def test_creates_parent_directory(self, tmp_path):
        """Should create parent directories if needed."""
        cache_file = tmp_path / "nested" / "cache" / "domains_cache.json"

        with patch("nextdns_blocker.config.get_domains_cache_file", return_value=cache_file):
            result = save_domains_cache({"domains": []})
            assert result is True
            assert cache_file.exists()


class TestFetchRemoteDomains:
    """Tests for fetch_remote_domains function."""

    @responses.activate
    def test_fetch_success_saves_cache(self, tmp_path):
        """Should fetch and cache domains on success."""
        cache_file = tmp_path / "domains_cache.json"
        url = "https://example.com/domains.json"
        data = {"domains": [{"domain": "example.com"}]}

        responses.add(responses.GET, url, json=data, status=200)

        with patch("nextdns_blocker.config.get_domains_cache_file", return_value=cache_file):
            result = fetch_remote_domains(url)

            assert result == data
            assert cache_file.exists()

    @responses.activate
    def test_fetch_failure_uses_cache(self, tmp_path):
        """Should fall back to cache on fetch failure."""
        cache_file = tmp_path / "domains_cache.json"
        url = "https://example.com/domains.json"
        cached_data = {"domains": [{"domain": "cached.com"}]}

        # Create existing cache
        cache_content = {"timestamp": time.time() - 3600, "data": cached_data}
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        cache_file.write_text(json.dumps(cache_content))

        responses.add(responses.GET, url, body=req.exceptions.ConnectionError("Network error"))

        with patch("nextdns_blocker.config.get_domains_cache_file", return_value=cache_file):
            result = fetch_remote_domains(url)

            assert result == cached_data

    @responses.activate
    def test_fetch_failure_no_cache_raises(self, tmp_path):
        """Should raise ConfigurationError when fetch fails and no cache."""
        cache_file = tmp_path / "nonexistent.json"
        url = "https://example.com/domains.json"

        responses.add(responses.GET, url, body=req.exceptions.ConnectionError("Network error"))

        with patch("nextdns_blocker.config.get_domains_cache_file", return_value=cache_file):
            with pytest.raises(ConfigurationError) as excinfo:
                fetch_remote_domains(url)

            assert "No cached data available" in str(excinfo.value)

    @responses.activate
    def test_fetch_invalid_json_raises(self, tmp_path):
        """Should raise ConfigurationError for invalid JSON response."""
        cache_file = tmp_path / "domains_cache.json"
        url = "https://example.com/domains.json"

        responses.add(responses.GET, url, body="not json", status=200)

        with patch("nextdns_blocker.config.get_domains_cache_file", return_value=cache_file):
            with pytest.raises(ConfigurationError) as excinfo:
                fetch_remote_domains(url, use_cache=False)

            assert "Invalid JSON" in str(excinfo.value)

    @responses.activate
    def test_fetch_non_object_raises(self, tmp_path):
        """Should raise ConfigurationError when response is not an object."""
        cache_file = tmp_path / "domains_cache.json"
        url = "https://example.com/domains.json"

        responses.add(responses.GET, url, json=["not", "an", "object"], status=200)

        with patch("nextdns_blocker.config.get_domains_cache_file", return_value=cache_file):
            with pytest.raises(ConfigurationError) as excinfo:
                fetch_remote_domains(url)

            assert "must be a JSON object" in str(excinfo.value)

    @responses.activate
    def test_disable_caching(self, tmp_path):
        """Should not use cache when use_cache=False."""
        cache_file = tmp_path / "domains_cache.json"
        url = "https://example.com/domains.json"

        responses.add(responses.GET, url, body=req.exceptions.ConnectionError("Network error"))

        with (
            patch("nextdns_blocker.config.get_domains_cache_file", return_value=cache_file),
            pytest.raises(ConfigurationError),
        ):
            fetch_remote_domains(url, use_cache=False)


class TestGetCacheStatus:
    """Tests for get_cache_status function."""

    def test_no_cache_exists(self, tmp_path):
        """Should report cache not existing."""
        cache_file = tmp_path / "nonexistent.json"

        with patch("nextdns_blocker.config.get_domains_cache_file", return_value=cache_file):
            status = get_cache_status()

            assert status["exists"] is False
            assert "path" in status

    def test_valid_cache(self, tmp_path):
        """Should report valid cache status."""
        cache_file = tmp_path / "domains_cache.json"
        cache_data = {"timestamp": time.time() - 600, "data": {"domains": []}}  # 10 minutes ago
        cache_file.write_text(json.dumps(cache_data))

        with patch("nextdns_blocker.config.get_domains_cache_file", return_value=cache_file):
            status = get_cache_status()

            assert status["exists"] is True
            assert status["expired"] is False
            assert 500 < status["age_seconds"] < 700

    def test_expired_cache(self, tmp_path):
        """Should report expired cache status."""
        cache_file = tmp_path / "domains_cache.json"
        cache_data = {"timestamp": time.time() - 7200, "data": {"domains": []}}  # 2 hours ago
        cache_file.write_text(json.dumps(cache_data))

        with patch("nextdns_blocker.config.get_domains_cache_file", return_value=cache_file):
            status = get_cache_status()

            assert status["exists"] is True
            assert status["expired"] is True

    def test_corrupted_cache(self, tmp_path):
        """Should report corrupted cache status."""
        cache_file = tmp_path / "domains_cache.json"
        cache_file.write_text("not valid json")

        with patch("nextdns_blocker.config.get_domains_cache_file", return_value=cache_file):
            status = get_cache_status()

            assert status["exists"] is True
            assert status.get("corrupted") is True


class TestLoadDomainsWithCache:
    """Tests for load_domains with caching support."""

    @responses.activate
    def test_load_from_url_with_cache(self, tmp_path):
        """Should load from URL and cache the result."""
        cache_file = tmp_path / "domains_cache.json"
        url = "https://example.com/domains.json"
        data = {"domains": [{"domain": "example.com"}], "allowlist": []}

        responses.add(responses.GET, url, json=data, status=200)

        with patch("nextdns_blocker.config.get_domains_cache_file", return_value=cache_file):
            domains, allowlist = load_domains(str(tmp_path), domains_url=url)

            assert len(domains) == 1
            assert domains[0]["domain"] == "example.com"
            assert cache_file.exists()

    @responses.activate
    def test_fallback_to_cache_on_network_error(self, tmp_path):
        """Should use cached data when network fails."""
        cache_file = tmp_path / "cache" / "domains_cache.json"
        url = "https://example.com/domains.json"
        cached_data = {"domains": [{"domain": "cached.com"}], "allowlist": []}

        # Create existing cache
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        cache_content = {"timestamp": time.time() - 3600, "data": cached_data}
        cache_file.write_text(json.dumps(cache_content))

        responses.add(responses.GET, url, body=req.exceptions.ConnectionError("Network error"))

        with patch("nextdns_blocker.config.get_domains_cache_file", return_value=cache_file):
            domains, allowlist = load_domains(str(tmp_path), domains_url=url)

            assert len(domains) == 1
            assert domains[0]["domain"] == "cached.com"

    def test_load_from_local_file(self, tmp_path):
        """Should load from local file without caching."""
        domains_file = tmp_path / "domains.json"
        data = {"domains": [{"domain": "local.com"}], "allowlist": []}
        domains_file.write_text(json.dumps(data))

        domains, allowlist = load_domains(str(tmp_path))

        assert len(domains) == 1
        assert domains[0]["domain"] == "local.com"
