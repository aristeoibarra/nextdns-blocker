"""E2E tests for configuration module."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from nextdns_blocker.config import (
    get_config_dir,
    get_data_dir,
    get_log_dir,
    load_config,
    load_domains,
    validate_allowlist_config,
    validate_api_key,
    validate_domain_config,
    validate_no_overlap,
    validate_profile_id,
)
from nextdns_blocker.exceptions import ConfigurationError


class TestValidateApiKey:
    """Tests for API key validation."""

    def test_valid_api_key(self) -> None:
        """Test with valid API key."""
        assert validate_api_key("abcd1234efgh") is True

    def test_api_key_with_dashes(self) -> None:
        """Test API key with dashes."""
        assert validate_api_key("abcd-1234-efgh") is True

    def test_api_key_with_underscores(self) -> None:
        """Test API key with underscores."""
        assert validate_api_key("abcd_1234_efgh") is True

    def test_empty_api_key(self) -> None:
        """Test with empty API key."""
        assert validate_api_key("") is False

    def test_none_api_key(self) -> None:
        """Test with None API key."""
        assert validate_api_key(None) is False  # type: ignore

    def test_short_api_key(self) -> None:
        """Test API key that's too short."""
        assert validate_api_key("short") is False

    def test_non_string_api_key(self) -> None:
        """Test with non-string API key."""
        assert validate_api_key(12345678) is False  # type: ignore


class TestValidateProfileId:
    """Tests for profile ID validation."""

    def test_valid_profile_id(self) -> None:
        """Test with valid profile ID."""
        assert validate_profile_id("abc123") is True

    def test_profile_id_with_dashes(self) -> None:
        """Test profile ID with dashes."""
        assert validate_profile_id("abc-123") is True

    def test_empty_profile_id(self) -> None:
        """Test with empty profile ID."""
        assert validate_profile_id("") is False

    def test_none_profile_id(self) -> None:
        """Test with None profile ID."""
        assert validate_profile_id(None) is False  # type: ignore

    def test_short_profile_id(self) -> None:
        """Test profile ID that's too short."""
        assert validate_profile_id("ab") is False

    def test_non_string_profile_id(self) -> None:
        """Test with non-string profile ID."""
        assert validate_profile_id(123456) is False  # type: ignore


class TestGetConfigDir:
    """Tests for get_config_dir function."""

    def test_with_override(self, tmp_path: Path) -> None:
        """Test config dir with override."""
        override = tmp_path / "custom_config"
        result = get_config_dir(override)
        assert result == override

    def test_with_cwd_both_files(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test config dir uses CWD when .env exists (config lives in DB)."""
        env_file = tmp_path / ".env"
        env_file.write_text("TEST=value")
        monkeypatch.chdir(tmp_path)

        result = get_config_dir()
        assert result == tmp_path

    def test_with_cwd_env_only_uses_system_dir(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test config dir uses CWD when .env exists (config lives in DB, not config.json)."""
        env_file = tmp_path / ".env"
        env_file.write_text("TEST=value")
        monkeypatch.chdir(tmp_path)

        result = get_config_dir()
        # With SQLite migration, CWD is used when .env exists (config is in DB)
        assert result == tmp_path

    def test_with_cwd_config_only_uses_system_dir(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test config dir uses system dir when only config.json exists (no .env)."""
        config_file = tmp_path / "config.json"
        config_file.write_text('{"blocklist": []}')
        monkeypatch.chdir(tmp_path)

        result = get_config_dir()
        # Should NOT use CWD, should fall back to system config dir
        assert result != tmp_path
        assert "nextdns-blocker" in str(result)


class TestGetDataDir:
    """Tests for get_data_dir function."""

    def test_returns_path(self) -> None:
        """Test data dir returns a path."""
        result = get_data_dir()
        assert isinstance(result, Path)
        assert "nextdns-blocker" in str(result)


class TestGetLogDir:
    """Tests for get_log_dir function."""

    def test_returns_logs_subdir(self) -> None:
        """Test log dir is under data dir."""
        result = get_log_dir()
        assert result.name == "logs"
        assert "nextdns-blocker" in str(result)


class TestValidateDomainConfig:
    """Tests for domain configuration validation."""

    def test_valid_domain_no_schedule(self) -> None:
        """Test valid domain without schedule."""
        config: dict[str, Any] = {"domain": "example.com"}
        errors = validate_domain_config(config, 0)
        assert len(errors) == 0

    def test_missing_domain_field(self) -> None:
        """Test missing domain field."""
        config: dict[str, Any] = {}
        errors = validate_domain_config(config, 0)
        assert len(errors) == 1
        assert "Missing 'domain'" in errors[0]

    def test_empty_domain(self) -> None:
        """Test empty domain."""
        config: dict[str, Any] = {"domain": ""}
        errors = validate_domain_config(config, 0)
        assert len(errors) == 1
        assert "Empty or invalid" in errors[0]

    def test_invalid_domain_format(self) -> None:
        """Test invalid domain format."""
        config: dict[str, Any] = {"domain": "not-a-domain!"}
        errors = validate_domain_config(config, 0)
        assert len(errors) == 1
        assert "Invalid domain format" in errors[0]

    def test_schedule_not_dict(self) -> None:
        """Test schedule that's not a dict."""
        config: dict[str, Any] = {"domain": "example.com", "schedule": "invalid"}
        errors = validate_domain_config(config, 0)
        assert len(errors) == 1
        assert "must be a dictionary" in errors[0]

    def test_available_hours_not_list(self) -> None:
        """Test available_hours that's not a list."""
        config: dict[str, Any] = {
            "domain": "example.com",
            "schedule": {"available_hours": "not a list"},
        }
        errors = validate_domain_config(config, 0)
        assert len(errors) == 1
        assert "must be a list" in errors[0]

    def test_schedule_block_not_dict(self) -> None:
        """Test schedule block that's not a dict."""
        config: dict[str, Any] = {
            "domain": "example.com",
            "schedule": {"available_hours": ["not a dict"]},
        }
        errors = validate_domain_config(config, 0)
        assert len(errors) == 1
        assert "must be a dictionary" in errors[0]

    def test_invalid_day_name(self) -> None:
        """Test invalid day name in schedule."""
        config: dict[str, Any] = {
            "domain": "example.com",
            "schedule": {
                "available_hours": [
                    {
                        "days": ["funday"],
                        "time_ranges": [{"start": "09:00", "end": "17:00"}],
                    }
                ]
            },
        }
        errors = validate_domain_config(config, 0)
        assert len(errors) == 1
        assert "invalid day" in errors[0]

    def test_time_range_not_dict(self) -> None:
        """Test time_range that's not a dict."""
        config: dict[str, Any] = {
            "domain": "example.com",
            "schedule": {
                "available_hours": [
                    {
                        "days": ["monday"],
                        "time_ranges": ["not a dict"],
                    }
                ]
            },
        }
        errors = validate_domain_config(config, 0)
        assert len(errors) == 1
        assert "must be a dictionary" in errors[0]

    def test_missing_start_time(self) -> None:
        """Test missing start time in time_range."""
        config: dict[str, Any] = {
            "domain": "example.com",
            "schedule": {
                "available_hours": [
                    {
                        "days": ["monday"],
                        "time_ranges": [{"end": "17:00"}],
                    }
                ]
            },
        }
        errors = validate_domain_config(config, 0)
        assert len(errors) == 1
        assert "missing 'start'" in errors[0]

    def test_missing_end_time(self) -> None:
        """Test missing end time in time_range."""
        config: dict[str, Any] = {
            "domain": "example.com",
            "schedule": {
                "available_hours": [
                    {
                        "days": ["monday"],
                        "time_ranges": [{"start": "09:00"}],
                    }
                ]
            },
        }
        errors = validate_domain_config(config, 0)
        assert len(errors) == 1
        assert "missing 'end'" in errors[0]

    def test_invalid_time_format(self) -> None:
        """Test invalid time format."""
        config: dict[str, Any] = {
            "domain": "example.com",
            "schedule": {
                "available_hours": [
                    {
                        "days": ["monday"],
                        "time_ranges": [{"start": "9am", "end": "5pm"}],
                    }
                ]
            },
        }
        errors = validate_domain_config(config, 0)
        assert len(errors) == 2  # Both start and end invalid


class TestValidateAllowlistConfig:
    """Tests for allowlist configuration validation."""

    def test_valid_allowlist_entry(self) -> None:
        """Test valid allowlist entry."""
        config: dict[str, Any] = {"domain": "example.com"}
        errors = validate_allowlist_config(config, 0)
        assert len(errors) == 0

    def test_missing_domain(self) -> None:
        """Test missing domain in allowlist."""
        config: dict[str, Any] = {}
        errors = validate_allowlist_config(config, 0)
        assert len(errors) == 1
        assert "Missing 'domain'" in errors[0]

    def test_valid_schedule_accepted(self) -> None:
        """Test that valid schedule in allowlist is accepted."""
        config: dict[str, Any] = {
            "domain": "youtube.com",
            "schedule": {
                "available_hours": [
                    {
                        "days": ["monday", "friday"],
                        "time_ranges": [{"start": "20:00", "end": "22:00"}],
                    }
                ]
            },
        }
        errors = validate_allowlist_config(config, 0)
        assert len(errors) == 0

    def test_empty_schedule_accepted(self) -> None:
        """Test that empty schedule in allowlist is accepted."""
        config: dict[str, Any] = {
            "domain": "example.com",
            "schedule": {"available_hours": []},
        }
        errors = validate_allowlist_config(config, 0)
        assert len(errors) == 0


class TestValidateNoOverlap:
    """Tests for overlap validation."""

    def test_no_overlap(self) -> None:
        """Test no overlap between lists."""
        domains = [{"domain": "example.com"}]
        allowlist = [{"domain": "other.com"}]
        errors = validate_no_overlap(domains, allowlist)
        assert len(errors) == 0

    def test_overlap_detected(self) -> None:
        """Test overlap is detected."""
        domains = [{"domain": "example.com"}]
        allowlist = [{"domain": "example.com"}]
        errors = validate_no_overlap(domains, allowlist)
        assert len(errors) == 1
        assert "example.com" in errors[0]


class TestLoadDomains:
    """Tests for loading domains (from database)."""

    def test_load_from_database(self, tmp_path: Path) -> None:
        """Test loading domains from database."""
        import nextdns_blocker.database as db

        db_path = tmp_path / "nextdns-blocker.db"
        with patch("nextdns_blocker.database.get_db_path", return_value=db_path):
            db.close_connection()
            db.init_database()
            db.add_blocked_domain("example.com")
            db.set_config("migrated", True)

            domains, allowlist = load_domains(str(tmp_path))

        assert len(domains) == 1
        assert domains[0]["domain"] == "example.com"

    def test_load_empty_db_raises(self, tmp_path: Path) -> None:
        """Test loading when database has no domains raises."""
        import nextdns_blocker.database as db

        db_path = tmp_path / "nextdns-blocker.db"
        with patch("nextdns_blocker.database.get_db_path", return_value=db_path):
            db.close_connection()
            db.init_database()
            # No domains, no migrated flag -> config_has_domains() is False

            with pytest.raises(ConfigurationError, match="No domains configured"):
                load_domains(str(tmp_path))

    @pytest.mark.skip(reason="Config is in DB; invalid JSON from file no longer applicable")
    def test_load_invalid_json(self, tmp_path: Path) -> None:
        """Test loading invalid JSON file (skipped: config now in DB)."""
        domains_file = tmp_path / "config.json"
        domains_file.write_text("not valid json")

        with pytest.raises(ConfigurationError, match="Invalid JSON"):
            load_domains(str(tmp_path))

    def test_load_no_domains_raises(self, tmp_path: Path) -> None:
        """Test loading when DB has schema but no domains raises."""
        import nextdns_blocker.database as db

        db_path = tmp_path / "nextdns-blocker.db"
        with patch("nextdns_blocker.database.get_db_path", return_value=db_path):
            db.close_connection()
            db.init_database()
            # Empty DB: config_has_domains() returns False

            with pytest.raises(ConfigurationError, match="No domains configured"):
                load_domains(str(tmp_path))


class TestLoadConfig:
    """Tests for loading configuration."""

    def test_load_config_success(self, tmp_path: Path) -> None:
        """Test successful config loading (API/profile from .env, timezone from DB)."""
        import nextdns_blocker.database as db

        env_file = tmp_path / ".env"
        env_file.write_text(
            "NEXTDNS_API_KEY=test-api-key\nNEXTDNS_PROFILE_ID=abc123\nTIMEZONE=UTC\n"
        )
        db_path = tmp_path / "nextdns-blocker.db"
        with patch("nextdns_blocker.database.get_db_path", return_value=db_path):
            db.close_connection()
            db.init_database()
            db.set_config("settings", {"timezone": "UTC", "editor": None})

        with patch("nextdns_blocker.database.get_db_path", return_value=db_path):
            config = load_config(tmp_path)

        assert config["api_key"] == "test-api-key"
        assert config["profile_id"] == "abc123"
        assert config["timezone"] == "UTC"

    def test_load_config_missing_api_key(self, tmp_path: Path) -> None:
        """Test config loading fails without API key."""
        env_file = tmp_path / ".env"
        env_file.write_text("NEXTDNS_PROFILE_ID=abc123\n")

        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ConfigurationError, match="Missing NEXTDNS_API_KEY"):
                load_config(tmp_path)

    def test_load_config_invalid_api_key(self, tmp_path: Path) -> None:
        """Test config loading fails with invalid API key."""
        env_file = tmp_path / ".env"
        env_file.write_text("NEXTDNS_API_KEY=short\nNEXTDNS_PROFILE_ID=abc123\n")

        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ConfigurationError, match="Invalid NEXTDNS_API_KEY"):
                load_config(tmp_path)

    def test_load_config_missing_profile_id(self, tmp_path: Path) -> None:
        """Test config loading fails without profile ID."""
        env_file = tmp_path / ".env"
        env_file.write_text("NEXTDNS_API_KEY=valid-api-key\n")

        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ConfigurationError, match="Missing NEXTDNS_PROFILE_ID"):
                load_config(tmp_path)

    def test_load_config_invalid_profile_id(self, tmp_path: Path) -> None:
        """Test config loading fails with invalid profile ID."""
        env_file = tmp_path / ".env"
        env_file.write_text("NEXTDNS_API_KEY=valid-api-key\nNEXTDNS_PROFILE_ID=ab\n")

        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ConfigurationError, match="Invalid NEXTDNS_PROFILE_ID"):
                load_config(tmp_path)

    def test_load_config_invalid_timezone(self, tmp_path: Path) -> None:
        """Test config loading fails with invalid timezone in database."""
        import nextdns_blocker.database as db

        env_file = tmp_path / ".env"
        env_file.write_text("NEXTDNS_API_KEY=valid-api-key\nNEXTDNS_PROFILE_ID=abc123\n")
        db_path = tmp_path / "nextdns-blocker.db"
        with patch("nextdns_blocker.database.get_db_path", return_value=db_path):
            db.close_connection()
            db.init_database()
            db.set_config("settings", {"timezone": "Invalid/TZ", "editor": None})

        with patch.dict(os.environ, {}, clear=True):
            with patch("nextdns_blocker.database.get_db_path", return_value=db_path):
                with pytest.raises(ConfigurationError, match="Invalid TIMEZONE"):
                    load_config(tmp_path)

    def test_load_config_with_quoted_values(self, tmp_path: Path) -> None:
        """Test config loading with quoted values in .env."""
        import nextdns_blocker.database as db

        env_file = tmp_path / ".env"
        env_file.write_text("NEXTDNS_API_KEY=\"test-api-key\"\nNEXTDNS_PROFILE_ID='abc123'\n")
        db_path = tmp_path / "nextdns-blocker.db"
        with patch("nextdns_blocker.database.get_db_path", return_value=db_path):
            db.close_connection()
            db.init_database()
            db.set_config("settings", {"timezone": "UTC", "editor": None})
        with patch("nextdns_blocker.database.get_db_path", return_value=db_path):
            config = load_config(tmp_path)

        assert config["api_key"] == "test-api-key"
        assert config["profile_id"] == "abc123"

    def test_load_config_skips_comments(self, tmp_path: Path) -> None:
        """Test config loading skips comment lines."""
        import nextdns_blocker.database as db

        env_file = tmp_path / ".env"
        env_file.write_text(
            "# This is a comment\n"
            "NEXTDNS_API_KEY=test-api-key\n"
            "# Another comment\n"
            "NEXTDNS_PROFILE_ID=abc123\n"
        )
        db_path = tmp_path / "nextdns-blocker.db"
        with patch("nextdns_blocker.database.get_db_path", return_value=db_path):
            db.close_connection()
            db.init_database()
            db.set_config("settings", {"timezone": "UTC", "editor": None})
        with patch("nextdns_blocker.database.get_db_path", return_value=db_path):
            config = load_config(tmp_path)

        assert config["api_key"] == "test-api-key"

    def test_load_config_handles_malformed_lines(self, tmp_path: Path) -> None:
        """Test config loading handles malformed lines gracefully."""
        import nextdns_blocker.database as db

        env_file = tmp_path / ".env"
        env_file.write_text(
            "NEXTDNS_API_KEY=test-api-key\n"
            "NEXTDNS_PROFILE_ID=abc123\n"
            "MALFORMED LINE WITHOUT EQUALS\n"
            "=empty_key\n"
        )
        db_path = tmp_path / "nextdns-blocker.db"
        with patch("nextdns_blocker.database.get_db_path", return_value=db_path):
            db.close_connection()
            db.init_database()
            db.set_config("settings", {"timezone": "UTC", "editor": None})
        with patch("nextdns_blocker.database.get_db_path", return_value=db_path):
            config = load_config(tmp_path)

        assert config["api_key"] == "test-api-key"

    def test_load_config_with_bom(self, tmp_path: Path) -> None:
        """Test config loading handles BOM in .env file."""
        import nextdns_blocker.database as db

        env_file = tmp_path / ".env"
        with open(env_file, "w", encoding="utf-8-sig") as f:
            f.write("NEXTDNS_API_KEY=test-api-key\n")
            f.write("NEXTDNS_PROFILE_ID=abc123\n")
        db_path = tmp_path / "nextdns-blocker.db"
        with patch("nextdns_blocker.database.get_db_path", return_value=db_path):
            db.close_connection()
            db.init_database()
            db.set_config("settings", {"timezone": "UTC", "editor": None})
        with patch("nextdns_blocker.database.get_db_path", return_value=db_path):
            config = load_config(tmp_path)

        assert config["api_key"] == "test-api-key"
