"""Tests for allowlist functionality."""

from unittest.mock import patch

import pytest
import responses
from click.testing import CliRunner

from nextdns_blocker.cli import main
from nextdns_blocker.client import (
    API_URL,
    AllowlistCache,
    NextDNSClient,
)
from nextdns_blocker.config import (
    load_domains,
    validate_allowlist_config,
    validate_no_overlap,
)
from nextdns_blocker.exceptions import (
    ConfigurationError,
    DomainValidationError,
)


class TestAllowlistCache:
    """Tests for AllowlistCache class."""

    def test_cache_init_empty(self):
        """Test cache initializes empty."""
        cache = AllowlistCache()
        assert cache.get() is None
        assert not cache.is_valid()

    def test_cache_set_and_get(self):
        """Test setting and getting cache data."""
        cache = AllowlistCache()
        data = [{"id": "aws.amazon.com", "active": True}]
        cache.set(data)
        assert cache.get() == data
        assert cache.is_valid()

    def test_cache_contains(self):
        """Test contains method."""
        cache = AllowlistCache()
        data = [{"id": "aws.amazon.com", "active": True}]
        cache.set(data)
        assert cache.contains("aws.amazon.com") is True
        assert cache.contains("unknown.com") is False

    def test_cache_contains_invalid(self):
        """Test contains returns None when cache invalid."""
        cache = AllowlistCache()
        assert cache.contains("aws.amazon.com") is None

    def test_cache_add_domain(self):
        """Test adding domain to cache."""
        cache = AllowlistCache()
        cache.set([])
        cache.add_domain("new.domain.com")
        assert cache.contains("new.domain.com") is True

    def test_cache_remove_domain(self):
        """Test removing domain from cache."""
        cache = AllowlistCache()
        cache.set([{"id": "aws.amazon.com", "active": True}])
        cache.remove_domain("aws.amazon.com")
        assert cache.contains("aws.amazon.com") is False

    def test_cache_invalidate(self):
        """Test cache invalidation."""
        cache = AllowlistCache()
        cache.set([{"id": "aws.amazon.com", "active": True}])
        cache.invalidate()
        assert cache.get() is None
        assert not cache.is_valid()


class TestGetAllowlist:
    """Tests for NextDNSClient.get_allowlist method."""

    @responses.activate
    def test_get_allowlist_success(self):
        """Test successful allowlist fetch."""
        client = NextDNSClient("testkey12345", "testprofile")

        responses.add(
            responses.GET,
            f"{API_URL}/profiles/testprofile/allowlist",
            json={"data": [{"id": "aws.amazon.com", "active": True}]},
            status=200,
        )

        result = client.get_allowlist()
        assert result == [{"id": "aws.amazon.com", "active": True}]

    @responses.activate
    def test_get_allowlist_empty(self):
        """Test empty allowlist fetch."""
        client = NextDNSClient("testkey12345", "testprofile")

        responses.add(
            responses.GET,
            f"{API_URL}/profiles/testprofile/allowlist",
            json={"data": []},
            status=200,
        )

        result = client.get_allowlist()
        assert result == []

    @responses.activate
    def test_get_allowlist_uses_cache(self):
        """Test that second call uses cache."""
        client = NextDNSClient("testkey12345", "testprofile")

        responses.add(
            responses.GET,
            f"{API_URL}/profiles/testprofile/allowlist",
            json={"data": [{"id": "aws.amazon.com", "active": True}]},
            status=200,
        )

        result1 = client.get_allowlist()
        result2 = client.get_allowlist()

        assert result1 == result2
        assert len(responses.calls) == 1  # Only one API call

    @responses.activate
    def test_get_allowlist_api_error(self):
        """Test allowlist fetch with API error."""
        client = NextDNSClient("testkey12345", "testprofile")

        responses.add(responses.GET, f"{API_URL}/profiles/testprofile/allowlist", status=500)

        result = client.get_allowlist(use_cache=False)
        assert result is None


class TestFindInAllowlist:
    """Tests for NextDNSClient.find_in_allowlist method."""

    @responses.activate
    def test_find_in_allowlist_exists(self):
        """Test finding domain that exists in allowlist."""
        client = NextDNSClient("testkey12345", "testprofile")

        responses.add(
            responses.GET,
            f"{API_URL}/profiles/testprofile/allowlist",
            json={"data": [{"id": "aws.amazon.com", "active": True}]},
            status=200,
        )

        result = client.find_in_allowlist("aws.amazon.com")
        assert result == "aws.amazon.com"

    @responses.activate
    def test_find_in_allowlist_not_found(self):
        """Test finding domain that doesn't exist in allowlist."""
        client = NextDNSClient("testkey12345", "testprofile")

        responses.add(
            responses.GET,
            f"{API_URL}/profiles/testprofile/allowlist",
            json={"data": []},
            status=200,
        )

        result = client.find_in_allowlist("aws.amazon.com")
        assert result is None


class TestAllow:
    """Tests for NextDNSClient.allow method."""

    @responses.activate
    def test_allow_new_domain(self):
        """Test allowing a new domain."""
        client = NextDNSClient("testkey12345", "testprofile")

        responses.add(
            responses.GET,
            f"{API_URL}/profiles/testprofile/allowlist",
            json={"data": []},
            status=200,
        )
        responses.add(
            responses.POST,
            f"{API_URL}/profiles/testprofile/allowlist",
            json={"success": True},
            status=200,
        )

        result = client.allow("aws.amazon.com")
        assert result is True

    @responses.activate
    def test_allow_already_allowed(self):
        """Test allowing domain already in allowlist."""
        client = NextDNSClient("testkey12345", "testprofile")

        responses.add(
            responses.GET,
            f"{API_URL}/profiles/testprofile/allowlist",
            json={"data": [{"id": "aws.amazon.com", "active": True}]},
            status=200,
        )

        result = client.allow("aws.amazon.com")
        assert result is True
        assert len(responses.calls) == 1  # No POST call

    def test_allow_invalid_domain(self):
        """Test allowing invalid domain raises error."""
        client = NextDNSClient("testkey12345", "testprofile")

        with pytest.raises(DomainValidationError):
            client.allow("invalid domain!")


class TestDisallow:
    """Tests for NextDNSClient.disallow method."""

    @responses.activate
    def test_disallow_existing_domain(self):
        """Test removing domain from allowlist."""
        client = NextDNSClient("testkey12345", "testprofile")

        responses.add(
            responses.GET,
            f"{API_URL}/profiles/testprofile/allowlist",
            json={"data": [{"id": "aws.amazon.com", "active": True}]},
            status=200,
        )
        responses.add(
            responses.DELETE,
            f"{API_URL}/profiles/testprofile/allowlist/aws.amazon.com",
            json={"success": True},
            status=200,
        )

        result = client.disallow("aws.amazon.com")
        assert result is True

    @responses.activate
    def test_disallow_not_in_allowlist(self):
        """Test disallowing domain not in allowlist."""
        client = NextDNSClient("testkey12345", "testprofile")

        responses.add(
            responses.GET,
            f"{API_URL}/profiles/testprofile/allowlist",
            json={"data": []},
            status=200,
        )

        result = client.disallow("aws.amazon.com")
        assert result is True
        assert len(responses.calls) == 1  # No DELETE call

    def test_disallow_invalid_domain(self):
        """Test disallowing invalid domain raises error."""
        client = NextDNSClient("testkey12345", "testprofile")

        with pytest.raises(DomainValidationError):
            client.disallow("invalid domain!")


class TestValidateAllowlistConfig:
    """Tests for validate_allowlist_config function."""

    def test_valid_config(self):
        """Test valid allowlist config."""
        config = {"domain": "aws.amazon.com", "description": "AWS Console"}
        errors = validate_allowlist_config(config, 0)
        assert errors == []

    def test_missing_domain(self):
        """Test config without domain field."""
        config = {"description": "No domain"}
        errors = validate_allowlist_config(config, 0)
        assert len(errors) == 1
        assert "Missing 'domain'" in errors[0]

    def test_empty_domain(self):
        """Test config with empty domain."""
        config = {"domain": ""}
        errors = validate_allowlist_config(config, 0)
        assert len(errors) == 1
        assert "Empty or invalid" in errors[0]

    def test_invalid_domain_format(self):
        """Test config with invalid domain format."""
        config = {"domain": "invalid_domain!@#"}
        errors = validate_allowlist_config(config, 0)
        assert len(errors) == 1
        assert "Invalid domain format" in errors[0]

    def test_valid_schedule_accepted(self):
        """Test that valid schedule is accepted in allowlist."""
        config = {
            "domain": "youtube.com",
            "schedule": {
                "available_hours": [
                    {
                        "days": ["monday", "tuesday", "wednesday"],
                        "time_ranges": [{"start": "20:00", "end": "22:00"}],
                    }
                ]
            },
        }
        errors = validate_allowlist_config(config, 0)
        assert errors == []

    def test_invalid_schedule_rejected(self):
        """Test that invalid schedule generates errors."""
        config = {
            "domain": "youtube.com",
            "schedule": {
                "available_hours": [
                    {
                        "days": ["invalid_day"],
                        "time_ranges": [{"start": "25:00", "end": "22:00"}],
                    }
                ]
            },
        }
        errors = validate_allowlist_config(config, 0)
        assert len(errors) >= 1
        # Should have errors for invalid day and invalid time format
        error_text = " ".join(errors)
        assert "invalid day" in error_text or "invalid time" in error_text

    def test_empty_schedule_accepted(self):
        """Test that empty schedule (no available_hours) is accepted."""
        config = {"domain": "aws.amazon.com", "schedule": {"available_hours": []}}
        errors = validate_allowlist_config(config, 0)
        assert errors == []

    def test_null_schedule_ok(self):
        """Test that null schedule is ok (always in allowlist)."""
        config = {"domain": "aws.amazon.com", "schedule": None}
        errors = validate_allowlist_config(config, 0)
        assert errors == []

    def test_schedule_missing_time_ranges(self):
        """Test schedule with missing time_ranges."""
        config = {
            "domain": "youtube.com",
            "schedule": {"available_hours": [{"days": ["monday"]}]},  # Missing time_ranges
        }
        errors = validate_allowlist_config(config, 0)
        # Should be valid - empty time_ranges is allowed
        assert errors == []


class TestValidateNoOverlap:
    """Tests for validate_no_overlap function."""

    def test_no_overlap(self):
        """Test with no overlap between lists."""
        domains = [{"domain": "amazon.com"}]
        allowlist = [{"domain": "aws.amazon.com"}]
        errors = validate_no_overlap(domains, allowlist)
        assert errors == []

    def test_overlap_detected(self):
        """Test that overlap is detected."""
        domains = [{"domain": "example.com"}]
        allowlist = [{"domain": "example.com"}]
        errors = validate_no_overlap(domains, allowlist)
        assert len(errors) == 1
        assert "both" in errors[0]

    def test_overlap_case_insensitive(self):
        """Test that overlap detection is case insensitive."""
        domains = [{"domain": "Example.COM"}]
        allowlist = [{"domain": "example.com"}]
        errors = validate_no_overlap(domains, allowlist)
        assert len(errors) == 1

    def test_empty_lists(self):
        """Test with empty lists."""
        errors = validate_no_overlap([], [])
        assert errors == []


class TestAllowCommand:
    """Tests for allow CLI command."""

    @pytest.fixture
    def runner(self):
        """Create Click CLI test runner."""
        return CliRunner()

    @patch("nextdns_blocker.cli.NextDNSClient")
    @patch("nextdns_blocker.cli.audit_log")
    def test_allow_success(self, mock_audit, mock_client_cls, runner, tmp_path):
        """Test successful allow command."""
        env_file = tmp_path / ".env"
        env_file.write_text("NEXTDNS_API_KEY=testkey12345\nNEXTDNS_PROFILE_ID=testprofile\n")

        mock_client = mock_client_cls.return_value
        mock_client.find_in_allowlist.return_value = None
        mock_client.allow.return_value = True
        mock_client.is_blocked.return_value = False

        result = runner.invoke(main, ["allow", "aws.amazon.com", "--config-dir", str(tmp_path)])

        assert result.exit_code == 0
        assert "allowlist" in result.output.lower()

    def test_allow_invalid_domain(self, runner, tmp_path):
        """Test allow with invalid domain."""
        env_file = tmp_path / ".env"
        env_file.write_text("NEXTDNS_API_KEY=testkey12345\nNEXTDNS_PROFILE_ID=testprofile\n")

        result = runner.invoke(main, ["allow", "invalid domain!", "--config-dir", str(tmp_path)])
        assert result.exit_code == 1
        assert "Invalid domain" in result.output

    @patch("nextdns_blocker.cli.NextDNSClient")
    @patch("nextdns_blocker.cli.audit_log")
    def test_allow_warns_if_in_denylist(self, mock_audit, mock_client_cls, runner, tmp_path):
        """Test allow warns if domain is in denylist."""
        env_file = tmp_path / ".env"
        env_file.write_text("NEXTDNS_API_KEY=testkey12345\nNEXTDNS_PROFILE_ID=testprofile\n")

        mock_client = mock_client_cls.return_value
        mock_client.find_in_allowlist.return_value = None
        mock_client.allow.return_value = True
        mock_client.is_blocked.return_value = True  # Domain IS in denylist

        result = runner.invoke(main, ["allow", "aws.amazon.com", "--config-dir", str(tmp_path)])

        assert result.exit_code == 0
        assert "Warning" in result.output or "warning" in result.output.lower()


class TestDisallowCommand:
    """Tests for disallow CLI command."""

    @pytest.fixture
    def runner(self):
        """Create Click CLI test runner."""
        return CliRunner()

    @responses.activate
    def test_disallow_success(self, runner, tmp_path):
        """Test successful disallow command."""
        responses.add(
            responses.GET,
            f"{API_URL}/profiles/testprofile/allowlist",
            json={"data": [{"id": "aws.amazon.com", "active": True}]},
            status=200,
        )
        responses.add(
            responses.DELETE,
            f"{API_URL}/profiles/testprofile/allowlist/aws.amazon.com",
            json={"success": True},
            status=200,
        )

        env_file = tmp_path / ".env"
        env_file.write_text("NEXTDNS_API_KEY=testkey12345\nNEXTDNS_PROFILE_ID=testprofile\n")

        with patch("nextdns_blocker.cli.audit_log"):
            result = runner.invoke(
                main, ["disallow", "aws.amazon.com", "--config-dir", str(tmp_path)]
            )

        assert result.exit_code == 0
        assert "allowlist" in result.output.lower()

    def test_disallow_invalid_domain(self, runner, tmp_path):
        """Test disallow with invalid domain."""
        env_file = tmp_path / ".env"
        env_file.write_text("NEXTDNS_API_KEY=testkey12345\nNEXTDNS_PROFILE_ID=testprofile\n")

        result = runner.invoke(main, ["disallow", "invalid domain!", "--config-dir", str(tmp_path)])
        assert result.exit_code == 1
        assert "Invalid domain" in result.output


class TestLoadDomainsWithAllowlist:
    """Tests for load_domains with allowlist support."""

    def test_load_domains_with_allowlist(self, tmp_path):
        """Test loading config.json with allowlist."""
        import json

        config = {
            "blocklist": [{"domain": "amazon.com", "schedule": None}],
            "allowlist": [{"domain": "aws.amazon.com"}],
        }
        json_file = tmp_path / "config.json"
        with open(json_file, "w") as f:
            json.dump(config, f)

        domains, allowlist = load_domains(str(tmp_path))

        assert len(domains) == 1
        assert domains[0]["domain"] == "amazon.com"
        assert len(allowlist) == 1
        assert allowlist[0]["domain"] == "aws.amazon.com"

    def test_load_domains_without_allowlist(self, tmp_path):
        """Test loading config.json without allowlist key."""
        import json

        config = {"blocklist": [{"domain": "amazon.com", "schedule": None}]}
        json_file = tmp_path / "config.json"
        with open(json_file, "w") as f:
            json.dump(config, f)

        domains, allowlist = load_domains(str(tmp_path))

        assert len(domains) == 1
        assert allowlist == []

    def test_load_domains_overlap_error(self, tmp_path):
        """Test that overlap between domains and allowlist raises error."""
        import json

        config = {
            "blocklist": [{"domain": "example.com", "schedule": None}],
            "allowlist": [{"domain": "example.com"}],
        }
        json_file = tmp_path / "config.json"
        with open(json_file, "w") as f:
            json.dump(config, f)

        with pytest.raises(ConfigurationError) as exc_info:
            load_domains(str(tmp_path))

        assert "validation failed" in str(exc_info.value)


class TestSyncWithAllowlist:
    """Tests for sync command with allowlist support."""

    @pytest.fixture
    def runner(self):
        """Create Click CLI test runner."""
        return CliRunner()

    @responses.activate
    @patch("nextdns_blocker.client.time.sleep")
    def test_sync_adds_to_allowlist(self, mock_sleep, runner, tmp_path):
        """Test sync adds domains to allowlist."""
        responses.add(
            responses.GET,
            f"{API_URL}/profiles/testprofile/denylist",
            json={"data": []},
            status=200,
        )
        responses.add(
            responses.GET,
            f"{API_URL}/profiles/testprofile/allowlist",
            json={"data": []},
            status=200,
        )
        responses.add(
            responses.POST,
            f"{API_URL}/profiles/testprofile/denylist",
            json={"success": True},
            status=200,
        )
        responses.add(
            responses.POST,
            f"{API_URL}/profiles/testprofile/allowlist",
            json={"success": True},
            status=200,
        )

        env_file = tmp_path / ".env"
        env_file.write_text("NEXTDNS_API_KEY=testkey12345\nNEXTDNS_PROFILE_ID=testprofile\n")
        domains_file = tmp_path / "config.json"
        domains_file.write_text(
            '{"blocklist": [{"domain": "test.com", "schedule": null}], "allowlist": [{"domain": "aws.amazon.com"}]}'
        )

        pause_file = tmp_path / ".paused"
        with patch("nextdns_blocker.cli.get_pause_file", return_value=pause_file):
            with patch("nextdns_blocker.cli.audit_log"):
                result = runner.invoke(main, ["sync", "-v", "--config-dir", str(tmp_path)])

        assert result.exit_code == 0

    @responses.activate
    def test_sync_dry_run_shows_allowlist(self, runner, tmp_path):
        """Test dry-run shows what would be allowed."""
        responses.add(
            responses.GET,
            f"{API_URL}/profiles/testprofile/denylist",
            json={"data": []},
            status=200,
        )
        responses.add(
            responses.GET,
            f"{API_URL}/profiles/testprofile/allowlist",
            json={"data": []},
            status=200,
        )

        env_file = tmp_path / ".env"
        env_file.write_text("NEXTDNS_API_KEY=testkey12345\nNEXTDNS_PROFILE_ID=testprofile\n")
        domains_file = tmp_path / "config.json"
        domains_file.write_text(
            '{"blocklist": [{"domain": "test.com", "schedule": null}], "allowlist": [{"domain": "aws.amazon.com"}]}'
        )

        pause_file = tmp_path / ".paused"
        with patch("nextdns_blocker.cli.get_pause_file", return_value=pause_file):
            result = runner.invoke(main, ["sync", "--dry-run", "--config-dir", str(tmp_path)])

        assert result.exit_code == 0
        assert "DRY RUN" in result.output


class TestStatusWithAllowlist:
    """Tests for status command with allowlist support."""

    @pytest.fixture
    def runner(self):
        """Create Click CLI test runner."""
        return CliRunner()

    @responses.activate
    def test_status_shows_allowlist(self, runner, tmp_path):
        """Test status shows allowlist section."""
        responses.add(
            responses.GET,
            f"{API_URL}/profiles/testprofile/denylist",
            json={"data": []},
            status=200,
        )
        responses.add(
            responses.GET,
            f"{API_URL}/profiles/testprofile/allowlist",
            json={"data": [{"id": "aws.amazon.com", "active": True}]},
            status=200,
        )

        env_file = tmp_path / ".env"
        env_file.write_text("NEXTDNS_API_KEY=testkey12345\nNEXTDNS_PROFILE_ID=testprofile\n")
        domains_file = tmp_path / "config.json"
        domains_file.write_text(
            '{"blocklist": [{"domain": "test.com", "schedule": null}], "allowlist": [{"domain": "aws.amazon.com"}]}'
        )

        pause_file = tmp_path / ".paused"
        with patch("nextdns_blocker.cli.get_pause_file", return_value=pause_file):
            result = runner.invoke(main, ["status", "--config-dir", str(tmp_path)])

        assert result.exit_code == 0
        assert "Allowlist" in result.output
        assert "aws.amazon.com" in result.output
