"""Tests for configuration loading functions."""

import json
import os
from unittest.mock import MagicMock, patch

import pytest

from nextdns_blocker.common import (
    parse_env_value,
    safe_int,
    validate_domain,
    validate_url,
)
from nextdns_blocker.config import (
    load_config,
    load_domains,
)
from nextdns_blocker.exceptions import ConfigurationError


class TestValidateDomain:
    """Tests for validate_domain function."""

    def test_valid_simple_domain(self):
        assert validate_domain("example.com") is True

    def test_valid_subdomain(self):
        assert validate_domain("sub.example.com") is True

    def test_valid_deep_subdomain(self):
        assert validate_domain("a.b.c.example.com") is True

    def test_valid_domain_with_numbers(self):
        assert validate_domain("example123.com") is True

    def test_valid_domain_with_hyphens(self):
        assert validate_domain("my-example.com") is True

    def test_empty_domain(self):
        assert validate_domain("") is False

    def test_none_domain(self):
        assert validate_domain(None) is False

    def test_domain_too_long(self):
        # Max domain length is 253 characters
        long_domain = "a" * 254 + ".com"
        assert validate_domain(long_domain) is False

    def test_domain_with_spaces(self):
        assert validate_domain("example .com") is False

    def test_domain_with_underscore(self):
        # Underscores are not valid in domain names per RFC
        assert validate_domain("example_test.com") is False

    def test_domain_starting_with_hyphen(self):
        assert validate_domain("-example.com") is False

    def test_domain_ending_with_hyphen(self):
        assert validate_domain("example-.com") is False

    def test_domain_with_special_chars(self):
        assert validate_domain("example!.com") is False
        assert validate_domain("example@.com") is False


class TestLoadConfig:
    """Tests for load_config function."""

    def test_load_config_with_env_vars(self, mock_env_vars):
        """Test that config loads required environment variables."""
        # This test verifies that the function reads from environment
        # The actual function call happens in integration tests
        assert os.environ.get("NEXTDNS_API_KEY") == mock_env_vars["NEXTDNS_API_KEY"]
        assert os.environ.get("NEXTDNS_PROFILE_ID") == mock_env_vars["NEXTDNS_PROFILE_ID"]

    def test_load_config_missing_api_key(self, temp_dir):
        """Test that missing API key raises ConfigurationError."""
        with patch.dict(os.environ, {"NEXTDNS_PROFILE_ID": "test"}, clear=True):
            with patch("nextdns_blocker.config.Path") as mock_path:
                mock_script_dir = MagicMock()
                mock_script_dir.__truediv__ = lambda self, x: temp_dir / x
                mock_script_dir.absolute.return_value = temp_dir
                mock_path.return_value.parent.absolute.return_value = temp_dir

                # Create empty .env file
                env_file = temp_dir / ".env"
                env_file.touch()

                # Unset API key if present
                os.environ.pop("NEXTDNS_API_KEY", None)
                os.environ.pop("NEXTDNS_PROFILE_ID", None)

                with pytest.raises(ConfigurationError) as exc_info:
                    load_config()

                assert "NEXTDNS_API_KEY" in str(exc_info.value)

    def test_load_config_missing_profile_id(self, temp_dir):
        """Test that missing profile ID raises ConfigurationError."""
        # Create .env with only API key (no profile ID)
        env_file = temp_dir / ".env"
        env_file.write_text("NEXTDNS_API_KEY=testkey12345\n")

        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ConfigurationError) as exc_info:
                load_config(config_dir=temp_dir)

            assert "NEXTDNS_PROFILE_ID" in str(exc_info.value)


class TestLoadDomains:
    """Tests for load_domains function."""

    def test_load_domains_from_file(self, temp_dir, domains_json_content):
        """Test loading domains from local JSON file."""
        json_file = temp_dir / "config.json"
        with open(json_file, "w") as f:
            json.dump(domains_json_content, f)

        domains, allowlist = load_domains(str(temp_dir))

        assert len(domains) == 2
        assert domains[0]["domain"] == "example.com"
        assert domains[1]["domain"] == "blocked.com"
        assert allowlist == []  # No allowlist in default fixture

    def test_load_domains_file_not_found(self, temp_dir):
        """Test that missing config.json raises ConfigurationError."""
        with pytest.raises(ConfigurationError) as exc_info:
            load_domains(str(temp_dir))

        assert "not found" in str(exc_info.value)

    def test_load_domains_invalid_json(self, temp_dir):
        """Test that invalid JSON raises ConfigurationError."""
        json_file = temp_dir / "config.json"
        with open(json_file, "w") as f:
            f.write("{ invalid json }")

        with pytest.raises(ConfigurationError) as exc_info:
            load_domains(str(temp_dir))

        assert "Invalid JSON" in str(exc_info.value)

    def test_load_domains_empty_domains_list(self, temp_dir):
        """Test that empty domains list raises ConfigurationError."""
        json_file = temp_dir / "config.json"
        with open(json_file, "w") as f:
            json.dump({"blocklist": []}, f)

        with pytest.raises(ConfigurationError) as exc_info:
            load_domains(str(temp_dir))

        assert "No domains" in str(exc_info.value)

    def test_load_domains_validation_errors(self, temp_dir, invalid_domains_json):
        """Test that validation errors raise ConfigurationError."""
        json_file = temp_dir / "config.json"
        with open(json_file, "w") as f:
            json.dump(invalid_domains_json, f)

        with pytest.raises(ConfigurationError) as exc_info:
            load_domains(str(temp_dir))

        assert "validation failed" in str(exc_info.value)

    def test_load_domains_not_dict(self, temp_dir):
        """Test that non-dict config raises ConfigurationError."""
        json_file = temp_dir / "config.json"
        with open(json_file, "w") as f:
            json.dump(["just", "a", "list"], f)

        with pytest.raises(ConfigurationError) as exc_info:
            load_domains(str(temp_dir))

        assert "must be a JSON object" in str(exc_info.value)


class TestDomainConfigValidation:
    """Additional tests for domain config validation with new domain validation."""

    def test_invalid_domain_format_detected(self, temp_dir):
        """Test that invalid domain format is detected during loading."""
        invalid_config = {"blocklist": [{"domain": "invalid_domain!@#"}]}
        json_file = temp_dir / "config.json"
        with open(json_file, "w") as f:
            json.dump(invalid_config, f)

        with pytest.raises(ConfigurationError) as exc_info:
            load_domains(str(temp_dir))

        # The error message indicates validation failed
        assert "validation failed" in str(exc_info.value)

    def test_valid_domain_passes_validation(self, temp_dir):
        """Test that valid domains pass validation."""
        valid_config = {
            "blocklist": [{"domain": "valid-domain.com"}, {"domain": "sub.domain.example.org"}]
        }
        json_file = temp_dir / "config.json"
        with open(json_file, "w") as f:
            json.dump(valid_config, f)

        domains, allowlist = load_domains(str(temp_dir))
        assert len(domains) == 2
        assert allowlist == []


class TestParseEnvValue:
    """Tests for parse_env_value function."""

    def test_parse_simple_value(self):
        """Test parsing simple value without quotes."""
        assert parse_env_value("simple_value") == "simple_value"

    def test_parse_double_quoted_value(self):
        """Test parsing double-quoted value."""
        assert parse_env_value('"quoted value"') == "quoted value"

    def test_parse_single_quoted_value(self):
        """Test parsing single-quoted value."""
        assert parse_env_value("'single quoted'") == "single quoted"

    def test_parse_value_with_whitespace(self):
        """Test parsing value with leading/trailing whitespace."""
        assert parse_env_value("  spaced  ") == "spaced"

    def test_parse_quoted_with_whitespace(self):
        """Test parsing quoted value with internal whitespace."""
        assert parse_env_value('"  spaces inside  "') == "  spaces inside  "

    def test_parse_empty_value(self):
        """Test parsing empty value."""
        assert parse_env_value("") == ""

    def test_parse_short_value(self):
        """Test parsing single character value."""
        assert parse_env_value("a") == "a"


class TestSafeInt:
    """Tests for safe_int function."""

    def test_safe_int_valid_number(self):
        """Test conversion of valid integer string."""
        assert safe_int("42", 0, "test") == 42

    def test_safe_int_none_returns_default(self):
        """Test None returns default value."""
        assert safe_int(None, 10, "test") == 10

    def test_safe_int_invalid_raises(self):
        """Test invalid string raises ConfigurationError."""
        with pytest.raises(ConfigurationError) as exc_info:
            safe_int("not_a_number", 0, "TEST_VAR")
        assert "TEST_VAR" in str(exc_info.value)
        assert "valid integer" in str(exc_info.value)

    def test_safe_int_negative_raises(self):
        """Test negative number raises ConfigurationError."""
        with pytest.raises(ConfigurationError) as exc_info:
            safe_int("-5", 0, "TEST_VAR")
        assert "non-negative integer" in str(exc_info.value)

    def test_safe_int_zero_valid(self):
        """Test zero is valid."""
        assert safe_int("0", 10, "test") == 0


class TestLoadConfigWithEnvFile:
    """Tests for load_config with .env file parsing."""

    def test_load_config_parses_env_file(self, temp_dir):
        """Test that load_config parses .env file correctly."""
        env_content = """
# Comment line
NEXTDNS_API_KEY=testapikey123
NEXTDNS_PROFILE_ID=testprofile

TIMEZONE=America/New_York
API_TIMEOUT=30
API_RETRIES=5
"""
        env_file = temp_dir / ".env"
        env_file.write_text(env_content)

        # Clear existing env vars
        with patch.dict(os.environ, {}, clear=True):
            config = load_config(config_dir=temp_dir)

            assert config["api_key"] == "testapikey123"
            assert config["profile_id"] == "testprofile"
            assert config["timezone"] == "America/New_York"
            assert config["timeout"] == 30
            assert config["retries"] == 5

    def test_load_config_invalid_timezone_raises(self, temp_dir):
        """Test that invalid timezone raises ConfigurationError."""
        env_content = """
NEXTDNS_API_KEY=testkey12345
NEXTDNS_PROFILE_ID=testprofile
TIMEZONE=Invalid/Timezone
"""
        env_file = temp_dir / ".env"
        env_file.write_text(env_content)

        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ConfigurationError) as exc_info:
                load_config(config_dir=temp_dir)
            assert "Invalid TIMEZONE" in str(exc_info.value)

    def test_load_config_skips_invalid_lines(self, temp_dir):
        """Test that invalid lines in .env are skipped."""
        env_content = """
NEXTDNS_API_KEY=testkey12345
NEXTDNS_PROFILE_ID=testprofile
invalid_line_no_equals
=empty_key
TIMEZONE=UTC
"""
        env_file = temp_dir / ".env"
        env_file.write_text(env_content)

        with patch.dict(os.environ, {}, clear=True):
            # Should not raise, just skip invalid lines
            config = load_config(config_dir=temp_dir)
            assert config["api_key"] == "testkey12345"

    def test_load_config_quoted_values(self, temp_dir):
        """Test that quoted values in .env are parsed correctly."""
        env_content = """
NEXTDNS_API_KEY="quotedkey123"
NEXTDNS_PROFILE_ID='singlequoted'
TIMEZONE=UTC
"""
        env_file = temp_dir / ".env"
        env_file.write_text(env_content)

        with patch.dict(os.environ, {}, clear=True):
            config = load_config(config_dir=temp_dir)
            assert config["api_key"] == "quotedkey123"
            assert config["profile_id"] == "singlequoted"

    def test_load_config_handles_bom(self, temp_dir):
        """Test that .env file with BOM is parsed correctly."""
        env_content = (
            "\ufeffNEXTDNS_API_KEY=bomkey12345\nNEXTDNS_PROFILE_ID=bomprofile\nTIMEZONE=UTC\n"
        )
        env_file = temp_dir / ".env"
        env_file.write_text(env_content, encoding="utf-8")

        with patch.dict(os.environ, {}, clear=True):
            config = load_config(config_dir=temp_dir)
            assert config["api_key"] == "bomkey12345"
            assert config["profile_id"] == "bomprofile"


class TestValidateUrl:
    """Tests for validate_url function."""

    def test_valid_https_url(self):
        """Test valid HTTPS URL."""
        assert validate_url("https://example.com") is True

    def test_valid_http_url(self):
        """Test valid HTTP URL."""
        assert validate_url("http://example.com") is True

    def test_valid_url_with_path(self):
        """Test valid URL with path."""
        assert validate_url("https://example.com/path/to/file.json") is True

    def test_valid_url_with_query(self):
        """Test valid URL with query string."""
        assert validate_url("https://example.com/file?key=value") is True

    def test_invalid_url_no_protocol(self):
        """Test URL without protocol is rejected."""
        assert validate_url("example.com") is False

    def test_invalid_url_ftp(self):
        """Test FTP URL is rejected."""
        assert validate_url("ftp://example.com") is False

    def test_invalid_url_empty(self):
        """Test empty URL is rejected."""
        assert validate_url("") is False

    def test_invalid_url_none(self):
        """Test None URL is rejected."""
        assert validate_url(None) is False

    def test_invalid_url_spaces(self):
        """Test URL with spaces is rejected."""
        assert validate_url("https://example .com") is False
