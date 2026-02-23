"""Tests for common utility functions."""

import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from nextdns_blocker.common import (
    APP_NAME,
    MAX_DOMAIN_LENGTH,
    MAX_LABEL_LENGTH,
    NEXTDNS_CATEGORIES,
    NEXTDNS_SERVICES,
    VALID_DAYS,
    WEEKDAY_TO_DAY,
    audit_log,
    ensure_log_dir,
    ensure_naive_datetime,
    get_log_dir,
    is_subdomain,
    parse_env_value,
    read_secure_file,
    safe_int,
    validate_category_id,
    validate_domain,
    validate_time_format,
    validate_url,
    write_secure_file,
)
from nextdns_blocker.exceptions import ConfigurationError


class TestIsSubdomain:
    """Tests for is_subdomain function."""

    def test_valid_subdomain(self):
        """Test that direct subdomain is detected."""
        assert is_subdomain("aws.amazon.com", "amazon.com") is True

    def test_deep_subdomain(self):
        """Test that deep subdomains are detected."""
        assert is_subdomain("a.b.c.example.com", "example.com") is True

    def test_same_domain_not_subdomain(self):
        """Test that same domain is not considered a subdomain."""
        assert is_subdomain("amazon.com", "amazon.com") is False

    def test_unrelated_domains(self):
        """Test that unrelated domains return False."""
        assert is_subdomain("google.com", "amazon.com") is False

    def test_partial_match_not_subdomain(self):
        """Test that partial suffix match is not considered subdomain."""
        # 'notamazon.com' ends with 'amazon.com' but is not a subdomain
        assert is_subdomain("notamazon.com", "amazon.com") is False

    def test_case_insensitive(self):
        """Test that comparison is case insensitive."""
        assert is_subdomain("AWS.Amazon.COM", "amazon.com") is True
        assert is_subdomain("aws.amazon.com", "AMAZON.COM") is True

    def test_whitespace_handling(self):
        """Test that whitespace is stripped."""
        assert is_subdomain("  aws.amazon.com  ", "amazon.com") is True
        assert is_subdomain("aws.amazon.com", "  amazon.com  ") is True

    def test_empty_child(self):
        """Test that empty child returns False."""
        assert is_subdomain("", "amazon.com") is False

    def test_empty_parent(self):
        """Test that empty parent returns False."""
        assert is_subdomain("aws.amazon.com", "") is False

    def test_both_empty(self):
        """Test that both empty returns False."""
        assert is_subdomain("", "") is False

    def test_www_subdomain(self):
        """Test www subdomain detection."""
        assert is_subdomain("www.example.com", "example.com") is True

    def test_mail_subdomain(self):
        """Test mail subdomain detection."""
        assert is_subdomain("mail.google.com", "google.com") is True

    def test_nested_subdomain(self):
        """Test deeply nested subdomain."""
        assert is_subdomain("very.deep.nested.subdomain.example.org", "example.org") is True

    def test_tld_difference(self):
        """Test that different TLDs don't match."""
        assert is_subdomain("example.org", "example.com") is False
        assert is_subdomain("sub.example.org", "example.com") is False


class TestValidateDomain:
    """Tests for validate_domain function (existing tests may exist elsewhere)."""

    def test_valid_domain(self):
        """Test valid domain."""
        assert validate_domain("example.com") is True

    def test_valid_subdomain(self):
        """Test valid subdomain."""
        assert validate_domain("www.example.com") is True

    def test_invalid_domain_with_spaces(self):
        """Test invalid domain with spaces."""
        assert validate_domain("example .com") is False

    def test_empty_domain(self):
        """Test empty domain."""
        assert validate_domain("") is False

    def test_numeric_tld_rejected(self):
        """Test that numeric TLD is rejected (RFC 1123)."""
        assert validate_domain("example.123") is False

    def test_label_too_long(self):
        """Test that labels longer than 63 characters are rejected."""
        long_label = "a" * 64  # 64 characters, exceeds max of 63
        assert validate_domain(f"{long_label}.com") is False

    def test_label_at_max_length(self):
        """Test that labels at exactly 63 characters are valid."""
        max_label = "a" * 63  # Exactly 63 characters
        assert validate_domain(f"{max_label}.com") is True

    def test_wildcard_rejected_by_default(self):
        """Test that wildcard domains are rejected by default."""
        assert validate_domain("*.example.com") is False

    def test_wildcard_allowed_when_flag_set(self):
        """Test that wildcard domains are accepted when allow_wildcards=True."""
        assert validate_domain("*.example.com", allow_wildcards=True) is True

    def test_wildcard_needs_valid_domain(self):
        """Test that wildcard still validates the rest of the domain."""
        # Invalid because only one label after wildcard
        assert validate_domain("*.com", allow_wildcards=True) is False
        # Invalid because of spaces
        assert validate_domain("*.exa mple.com", allow_wildcards=True) is False

    def test_single_label_rejected(self):
        """Test that single-label domains are rejected (need at least domain.tld)."""
        assert validate_domain("localhost") is False

    def test_empty_label_rejected(self):
        """Test that empty labels (double dots) are rejected."""
        assert validate_domain("example..com") is False

    def test_leading_hyphen_rejected(self):
        """Test that labels starting with hyphen are rejected."""
        assert validate_domain("-example.com") is False

    def test_trailing_hyphen_rejected(self):
        """Test that labels ending with hyphen are rejected."""
        assert validate_domain("example-.com") is False

    def test_trailing_dot_rejected(self):
        """Test that trailing dot (FQDN notation) is rejected."""
        assert validate_domain("example.com.") is False

    def test_domain_too_long(self):
        """Test that domains exceeding 253 chars are rejected."""
        # Create a domain that exceeds MAX_DOMAIN_LENGTH (253)
        long_domain = (
            "a" * 50 + "." + "b" * 50 + "." + "c" * 50 + "." + "d" * 50 + "." + "e" * 50 + ".com"
        )
        assert len(long_domain) > MAX_DOMAIN_LENGTH
        assert validate_domain(long_domain) is False


class TestValidateTimeFormat:
    """Tests for validate_time_format function."""

    def test_valid_times(self):
        """Test valid time formats."""
        assert validate_time_format("00:00") is True
        assert validate_time_format("09:30") is True
        assert validate_time_format("12:00") is True
        assert validate_time_format("23:59") is True
        assert validate_time_format("9:30") is True  # Single digit hour

    def test_invalid_times(self):
        """Test invalid time formats."""
        assert validate_time_format("24:00") is False
        assert validate_time_format("12:60") is False
        assert validate_time_format("25:00") is False
        assert validate_time_format("12:99") is False

    def test_invalid_formats(self):
        """Test non-time strings."""
        assert validate_time_format("") is False
        assert validate_time_format("noon") is False
        assert validate_time_format("12") is False
        assert validate_time_format("12:00:00") is False  # Seconds not allowed
        assert validate_time_format(None) is False
        assert validate_time_format(1200) is False  # Not a string


class TestValidateUrl:
    """Tests for validate_url function."""

    def test_valid_urls(self):
        """Test valid URLs."""
        assert validate_url("https://example.com") is True
        assert validate_url("http://example.com") is True
        assert validate_url("https://example.com/path") is True
        assert validate_url("https://example.com/path/to/file") is True
        assert validate_url("https://example.com:8080") is True
        assert validate_url("https://sub.example.com") is True

    def test_invalid_urls(self):
        """Test invalid URLs."""
        assert validate_url("") is False
        assert validate_url("ftp://example.com") is False  # Not http/https
        assert validate_url("example.com") is False  # No scheme
        assert validate_url(None) is False
        assert validate_url(123) is False

    def test_invalid_port(self):
        """Test URLs with invalid ports."""
        assert validate_url("https://example.com:0") is False
        assert validate_url("https://example.com:65536") is False
        assert validate_url("https://example.com:99999") is False

    def test_leading_zero_port_rejected(self):
        """Test that leading zeros in port are rejected."""
        assert validate_url("https://example.com:08080") is False


class TestValidateCategoryId:
    """Tests for validate_category_id function."""

    def test_valid_category_ids(self):
        """Test valid category IDs."""
        assert validate_category_id("social") is True
        assert validate_category_id("social-media") is True
        assert validate_category_id("category1") is True
        assert validate_category_id("a") is True

    def test_invalid_category_ids(self):
        """Test invalid category IDs."""
        assert validate_category_id("") is False
        assert validate_category_id("1social") is False  # Can't start with number
        assert validate_category_id("-social") is False  # Can't start with hyphen
        assert validate_category_id("Social") is False  # Must be lowercase
        assert validate_category_id("social_media") is False  # Underscore not allowed
        assert validate_category_id(None) is False
        assert validate_category_id(123) is False

    def test_too_long_category_id(self):
        """Test that category IDs over 50 chars are rejected."""
        long_id = "a" * 51
        assert validate_category_id(long_id) is False


class TestParseEnvValue:
    """Tests for parse_env_value function."""

    def test_plain_value(self):
        """Test plain value without quotes."""
        assert parse_env_value("test_value") == "test_value"

    def test_double_quoted_value(self):
        """Test double-quoted value."""
        assert parse_env_value('"test_value"') == "test_value"

    def test_single_quoted_value(self):
        """Test single-quoted value."""
        assert parse_env_value("'test_value'") == "test_value"

    def test_value_with_whitespace(self):
        """Test value with surrounding whitespace."""
        assert parse_env_value("  test_value  ") == "test_value"

    def test_quoted_with_whitespace(self):
        """Test quoted value with surrounding whitespace."""
        assert parse_env_value('  "test_value"  ') == "test_value"

    def test_none_raises_error(self):
        """Test that None raises ValueError."""
        with pytest.raises(ValueError):
            parse_env_value(None)

    def test_non_string_raises_error(self):
        """Test that non-string raises ValueError."""
        with pytest.raises(ValueError):
            parse_env_value(123)


class TestSafeInt:
    """Tests for safe_int function."""

    def test_valid_integer_string(self):
        """Test valid integer string conversion."""
        assert safe_int("42", 0) == 42
        assert safe_int("0", 10) == 0
        assert safe_int("100", 0) == 100

    def test_none_returns_default(self):
        """Test that None returns default value."""
        assert safe_int(None, 10) == 10
        assert safe_int(None, 0) == 0

    def test_invalid_string_raises_error(self):
        """Test that invalid string raises ConfigurationError."""
        with pytest.raises(ConfigurationError):
            safe_int("not_a_number", 0, "test_value")

    def test_negative_raises_error(self):
        """Test that negative values raise ConfigurationError."""
        with pytest.raises(ConfigurationError):
            safe_int("-5", 0, "test_value")


class TestEnsureNaiveDatetime:
    """Tests for ensure_naive_datetime function."""

    def test_naive_datetime_unchanged(self):
        """Test that naive datetime is returned unchanged."""
        from datetime import datetime

        dt = datetime(2024, 1, 15, 12, 30)
        result = ensure_naive_datetime(dt)
        assert result == dt
        assert result.tzinfo is None

    def test_aware_datetime_stripped(self):
        """Test that aware datetime has timezone stripped."""
        from datetime import datetime, timezone

        dt = datetime(2024, 1, 15, 12, 30, tzinfo=timezone.utc)
        result = ensure_naive_datetime(dt)
        assert result.tzinfo is None
        assert result.year == 2024
        assert result.month == 1
        assert result.day == 15
        assert result.hour == 12
        assert result.minute == 30


class TestWriteAndReadSecureFile:
    """Tests for write_secure_file and read_secure_file functions."""

    def test_write_and_read_file(self, temp_dir):
        """Test writing and reading a secure file."""
        test_file = temp_dir / "test.txt"
        content = "Hello, World!"

        write_secure_file(test_file, content)
        result = read_secure_file(test_file)

        assert result == content

    def test_read_nonexistent_file(self, temp_dir):
        """Test reading a file that doesn't exist."""
        test_file = temp_dir / "nonexistent.txt"
        result = read_secure_file(test_file)
        assert result is None

    def test_overwrite_existing_file(self, temp_dir):
        """Test overwriting an existing file."""
        test_file = temp_dir / "test.txt"

        write_secure_file(test_file, "first content")
        write_secure_file(test_file, "second content")
        result = read_secure_file(test_file)

        assert result == "second content"

    def test_file_permissions(self, temp_dir):
        """Test that file is created with secure permissions."""
        test_file = temp_dir / "secure.txt"
        write_secure_file(test_file, "secret")

        # Check permissions (Unix only)
        if sys.platform != "win32":
            mode = os.stat(test_file).st_mode & 0o777
            assert mode == 0o600


class TestAuditLog:
    """Tests for audit_log function."""

    def test_audit_log_basic(self, temp_dir):
        """Test basic audit log entry."""
        with patch("nextdns_blocker.database.add_audit_log") as mock_add:
            audit_log("BLOCK", "example.com")
            mock_add.assert_called_once()
            call_args = mock_add.call_args
            assert call_args.kwargs["event_type"] == "BLOCK"
            assert call_args.kwargs["domain"] == "example.com"

    def test_audit_log_with_prefix(self, temp_dir):
        """Test audit log with prefix."""
        with patch("nextdns_blocker.database.add_audit_log") as mock_add:
            audit_log("SYNC", "example.com", prefix="WD")
            call_args = mock_add.call_args
            assert call_args.kwargs["event_type"] == "WD_SYNC"

    def test_audit_log_with_metadata(self, temp_dir):
        """Test audit log with key=value metadata."""
        with patch("nextdns_blocker.database.add_audit_log") as mock_add:
            audit_log("UNBLOCK", "example.com reason=manual")
            call_args = mock_add.call_args
            assert call_args.kwargs["metadata"]["reason"] == "manual"

    def test_audit_log_database_error_handled(self, temp_dir):
        """Test that database errors are handled gracefully."""
        with patch("nextdns_blocker.database.add_audit_log") as mock_add:
            mock_add.side_effect = Exception("DB error")
            # Should not raise
            audit_log("BLOCK", "example.com")


class TestConstants:
    """Tests for constants in common module."""

    def test_app_name(self):
        """Test APP_NAME constant."""
        assert APP_NAME == "nextdns-blocker"

    def test_valid_days(self):
        """Test VALID_DAYS contains all weekdays."""
        assert len(VALID_DAYS) == 7
        assert "monday" in VALID_DAYS
        assert "sunday" in VALID_DAYS

    def test_weekday_to_day(self):
        """Test WEEKDAY_TO_DAY mapping."""
        assert len(WEEKDAY_TO_DAY) == 7
        assert WEEKDAY_TO_DAY[0] == "monday"
        assert WEEKDAY_TO_DAY[6] == "sunday"

    def test_nextdns_categories(self):
        """Test NEXTDNS_CATEGORIES contains expected categories."""
        assert "porn" in NEXTDNS_CATEGORIES
        assert "gambling" in NEXTDNS_CATEGORIES
        assert "social-networks" in NEXTDNS_CATEGORIES

    def test_nextdns_services(self):
        """Test NEXTDNS_SERVICES contains expected services."""
        assert "youtube" in NEXTDNS_SERVICES
        assert "netflix" in NEXTDNS_SERVICES
        assert "discord" in NEXTDNS_SERVICES

    def test_max_lengths(self):
        """Test MAX constants."""
        assert MAX_DOMAIN_LENGTH == 253
        assert MAX_LABEL_LENGTH == 63


class TestGetLogDir:
    """Tests for get_log_dir function."""

    def test_get_log_dir_returns_path(self):
        """Test that get_log_dir returns a Path object."""
        result = get_log_dir()
        assert isinstance(result, Path)
        assert "logs" in str(result)

    def test_ensure_log_dir_creates_directory(self, temp_dir):
        """Test that ensure_log_dir creates the directory."""
        with patch("nextdns_blocker.common.get_log_dir") as mock_get:
            log_dir = temp_dir / "logs"
            mock_get.return_value = log_dir
            ensure_log_dir()
            assert log_dir.exists()
