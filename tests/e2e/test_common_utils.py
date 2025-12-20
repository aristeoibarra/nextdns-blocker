"""E2E tests for common utilities."""

from __future__ import annotations

import stat
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from nextdns_blocker.common import (
    APP_NAME,
    DAYS_MAP,
    DOMAIN_PATTERN,
    MAX_DOMAIN_LENGTH,
    MAX_LABEL_LENGTH,
    SECURE_FILE_MODE,
    TIME_PATTERN,
    URL_PATTERN,
    VALID_DAYS,
    audit_log,
    ensure_log_dir,
    get_audit_log_file,
    get_log_dir,
    parse_env_value,
    read_secure_file,
    safe_int,
    validate_domain,
    validate_time_format,
    validate_url,
    write_secure_file,
)
from nextdns_blocker.exceptions import ConfigurationError


class TestConstants:
    """Tests for module constants."""

    def test_app_name(self) -> None:
        """Test APP_NAME constant."""
        assert APP_NAME == "nextdns-blocker"

    def test_secure_file_mode(self) -> None:
        """Test SECURE_FILE_MODE is 0o600."""
        assert SECURE_FILE_MODE == stat.S_IRUSR | stat.S_IWUSR
        assert SECURE_FILE_MODE == 0o600

    def test_domain_length_constants(self) -> None:
        """Test domain length constants."""
        assert MAX_DOMAIN_LENGTH == 253
        assert MAX_LABEL_LENGTH == 63

    def test_valid_days(self) -> None:
        """Test VALID_DAYS contains all weekdays."""
        expected = {"monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"}
        assert expected == VALID_DAYS

    def test_days_map(self) -> None:
        """Test DAYS_MAP has correct weekday numbers."""
        assert DAYS_MAP["monday"] == 0
        assert DAYS_MAP["tuesday"] == 1
        assert DAYS_MAP["wednesday"] == 2
        assert DAYS_MAP["thursday"] == 3
        assert DAYS_MAP["friday"] == 4
        assert DAYS_MAP["saturday"] == 5
        assert DAYS_MAP["sunday"] == 6


class TestValidateDomain:
    """Tests for domain validation."""

    def test_valid_simple_domain(self) -> None:
        """Test simple domain is valid."""
        assert validate_domain("example.com") is True

    def test_valid_subdomain(self) -> None:
        """Test subdomain is valid."""
        assert validate_domain("www.example.com") is True

    def test_valid_multiple_subdomains(self) -> None:
        """Test multiple subdomains are valid."""
        assert validate_domain("sub.www.example.com") is True

    def test_valid_domain_with_numbers(self) -> None:
        """Test domain with numbers is valid."""
        assert validate_domain("example123.com") is True
        assert validate_domain("123example.com") is True

    def test_valid_domain_with_hyphens(self) -> None:
        """Test domain with hyphens is valid."""
        assert validate_domain("my-example.com") is True

    def test_invalid_empty_domain(self) -> None:
        """Test empty domain is invalid."""
        assert validate_domain("") is False

    def test_invalid_too_long_domain(self) -> None:
        """Test domain exceeding max length is invalid."""
        long_domain = "a" * 254 + ".com"
        assert validate_domain(long_domain) is False

    def test_invalid_trailing_dot(self) -> None:
        """Test domain with trailing dot is invalid."""
        assert validate_domain("example.com.") is False

    def test_invalid_domain_with_protocol(self) -> None:
        """Test domain with protocol is invalid."""
        assert validate_domain("https://example.com") is False

    def test_invalid_domain_with_path(self) -> None:
        """Test domain with path is invalid."""
        assert validate_domain("example.com/path") is False

    def test_invalid_domain_with_underscore(self) -> None:
        """Test domain with underscore is invalid."""
        assert validate_domain("exam_ple.com") is False

    def test_invalid_domain_starting_with_hyphen(self) -> None:
        """Test domain starting with hyphen is invalid."""
        assert validate_domain("-example.com") is False


class TestValidateTimeFormat:
    """Tests for time format validation."""

    def test_valid_time(self) -> None:
        """Test valid time formats."""
        assert validate_time_format("09:00") is True
        assert validate_time_format("17:30") is True
        assert validate_time_format("00:00") is True
        assert validate_time_format("23:59") is True

    def test_valid_single_digit_hour(self) -> None:
        """Test single digit hour is valid."""
        assert validate_time_format("9:00") is True

    def test_invalid_empty_time(self) -> None:
        """Test empty time is invalid."""
        assert validate_time_format("") is False

    def test_invalid_none_time(self) -> None:
        """Test None time is invalid."""
        assert validate_time_format(None) is False  # type: ignore

    def test_invalid_non_string_time(self) -> None:
        """Test non-string time is invalid."""
        assert validate_time_format(123) is False  # type: ignore

    def test_invalid_time_format(self) -> None:
        """Test invalid time formats."""
        assert validate_time_format("25:00") is False
        assert validate_time_format("12:60") is False
        assert validate_time_format("12:0") is False
        assert validate_time_format("12-00") is False


class TestValidateUrl:
    """Tests for URL validation."""

    def test_valid_http_url(self) -> None:
        """Test valid HTTP URL."""
        assert validate_url("http://example.com") is True

    def test_valid_https_url(self) -> None:
        """Test valid HTTPS URL."""
        assert validate_url("https://example.com") is True

    def test_valid_url_with_path(self) -> None:
        """Test valid URL with path."""
        assert validate_url("https://example.com/path/to/file.json") is True

    def test_valid_url_with_port(self) -> None:
        """Test valid URL with port."""
        assert validate_url("https://example.com:8080") is True
        assert validate_url("https://example.com:443/path") is True

    def test_invalid_empty_url(self) -> None:
        """Test empty URL is invalid."""
        assert validate_url("") is False

    def test_invalid_none_url(self) -> None:
        """Test None URL is invalid."""
        assert validate_url(None) is False  # type: ignore

    def test_invalid_non_string_url(self) -> None:
        """Test non-string URL is invalid."""
        assert validate_url(123) is False  # type: ignore

    def test_invalid_url_without_scheme(self) -> None:
        """Test URL without scheme is invalid."""
        assert validate_url("example.com") is False

    def test_invalid_url_with_ftp_scheme(self) -> None:
        """Test URL with FTP scheme is invalid."""
        assert validate_url("ftp://example.com") is False

    def test_invalid_port_out_of_range(self) -> None:
        """Test URL with port out of range is invalid."""
        assert validate_url("https://example.com:0") is False
        assert validate_url("https://example.com:65536") is False


class TestParseEnvValue:
    """Tests for .env value parsing."""

    def test_plain_value(self) -> None:
        """Test plain value without quotes."""
        assert parse_env_value("value") == "value"

    def test_value_with_whitespace(self) -> None:
        """Test value with surrounding whitespace."""
        assert parse_env_value("  value  ") == "value"

    def test_double_quoted_value(self) -> None:
        """Test double-quoted value."""
        assert parse_env_value('"quoted value"') == "quoted value"

    def test_single_quoted_value(self) -> None:
        """Test single-quoted value."""
        assert parse_env_value("'quoted value'") == "quoted value"

    def test_empty_value(self) -> None:
        """Test empty value."""
        assert parse_env_value("") == ""

    def test_quoted_whitespace(self) -> None:
        """Test quoted value with whitespace."""
        assert parse_env_value('  "value"  ') == "value"


class TestSafeInt:
    """Tests for safe integer conversion."""

    def test_valid_integer(self) -> None:
        """Test valid integer string."""
        assert safe_int("42", 0) == 42

    def test_none_returns_default(self) -> None:
        """Test None returns default."""
        assert safe_int(None, 100) == 100

    def test_zero_is_valid(self) -> None:
        """Test zero is valid."""
        assert safe_int("0", 10) == 0

    def test_negative_raises_error(self) -> None:
        """Test negative integer raises ConfigurationError."""
        with pytest.raises(ConfigurationError) as exc_info:
            safe_int("-1", 0, "test_value")

        assert "non-negative integer" in str(exc_info.value)

    def test_invalid_string_raises_error(self) -> None:
        """Test non-numeric string raises ConfigurationError."""
        with pytest.raises(ConfigurationError) as exc_info:
            safe_int("not_a_number", 0, "test_value")

        assert "valid integer" in str(exc_info.value)


class TestLogDirectoryFunctions:
    """Tests for log directory functions."""

    @patch("nextdns_blocker.common.user_data_dir")
    def test_get_log_dir(self, mock_data_dir: MagicMock) -> None:
        """Test get_log_dir returns correct path."""
        mock_data_dir.return_value = "/mock/data/dir"

        result = get_log_dir()

        assert result == Path("/mock/data/dir/logs")

    @patch("nextdns_blocker.common.get_log_dir")
    def test_get_audit_log_file(self, mock_log_dir: MagicMock) -> None:
        """Test get_audit_log_file returns correct path."""
        mock_log_dir.return_value = Path("/mock/logs")

        result = get_audit_log_file()

        assert result == Path("/mock/logs/audit.log")

    @patch("nextdns_blocker.common.get_log_dir")
    def test_ensure_log_dir_creates_directory(
        self, mock_log_dir: MagicMock, tmp_path: Path
    ) -> None:
        """Test ensure_log_dir creates the directory."""
        log_dir = tmp_path / "logs"
        mock_log_dir.return_value = log_dir

        ensure_log_dir()

        assert log_dir.exists()

    @patch("nextdns_blocker.common.get_log_dir")
    def test_ensure_log_dir_handles_existing(self, mock_log_dir: MagicMock, tmp_path: Path) -> None:
        """Test ensure_log_dir handles existing directory."""
        log_dir = tmp_path / "logs"
        log_dir.mkdir()
        mock_log_dir.return_value = log_dir

        ensure_log_dir()  # Should not raise

        assert log_dir.exists()


class TestAuditLog:
    """Tests for audit logging."""

    @patch("nextdns_blocker.common.get_log_dir")
    def test_audit_log_creates_entry(self, mock_log_dir: MagicMock, tmp_path: Path) -> None:
        """Test audit_log creates log entry."""
        log_dir = tmp_path / "logs"
        mock_log_dir.return_value = log_dir

        audit_log("BLOCK", "example.com")

        audit_file = log_dir / "audit.log"
        assert audit_file.exists()
        content = audit_file.read_text()
        assert "BLOCK" in content
        assert "example.com" in content

    @patch("nextdns_blocker.common.get_log_dir")
    def test_audit_log_with_prefix(self, mock_log_dir: MagicMock, tmp_path: Path) -> None:
        """Test audit_log with prefix."""
        log_dir = tmp_path / "logs"
        mock_log_dir.return_value = log_dir

        audit_log("CHECK", "jobs restored", prefix="WD")

        audit_file = log_dir / "audit.log"
        content = audit_file.read_text()
        assert "WD" in content
        assert "CHECK" in content

    @patch("nextdns_blocker.common.get_log_dir")
    def test_audit_log_appends(self, mock_log_dir: MagicMock, tmp_path: Path) -> None:
        """Test audit_log appends to existing file."""
        log_dir = tmp_path / "logs"
        mock_log_dir.return_value = log_dir

        audit_log("ACTION1", "detail1")
        audit_log("ACTION2", "detail2")

        audit_file = log_dir / "audit.log"
        content = audit_file.read_text()
        assert "ACTION1" in content
        assert "ACTION2" in content
        assert content.count("\n") == 2


class TestWriteSecureFile:
    """Tests for secure file writing."""

    @patch("nextdns_blocker.common.get_log_dir")
    def test_write_secure_file_creates_file(self, mock_log_dir: MagicMock, tmp_path: Path) -> None:
        """Test write_secure_file creates file."""
        mock_log_dir.return_value = tmp_path / "logs"
        file_path = tmp_path / "test.txt"

        write_secure_file(file_path, "test content")

        assert file_path.exists()
        assert file_path.read_text() == "test content"

    @patch("nextdns_blocker.common.get_log_dir")
    def test_write_secure_file_creates_parent_dirs(
        self, mock_log_dir: MagicMock, tmp_path: Path
    ) -> None:
        """Test write_secure_file creates parent directories."""
        mock_log_dir.return_value = tmp_path / "logs"
        file_path = tmp_path / "nested" / "path" / "test.txt"

        write_secure_file(file_path, "content")

        assert file_path.exists()

    @patch("nextdns_blocker.common.get_log_dir")
    def test_write_secure_file_overwrites(self, mock_log_dir: MagicMock, tmp_path: Path) -> None:
        """Test write_secure_file overwrites existing file."""
        mock_log_dir.return_value = tmp_path / "logs"
        file_path = tmp_path / "test.txt"
        file_path.write_text("old content")

        write_secure_file(file_path, "new content")

        assert file_path.read_text() == "new content"


class TestReadSecureFile:
    """Tests for secure file reading."""

    def test_read_secure_file_returns_content(self, tmp_path: Path) -> None:
        """Test read_secure_file returns file content."""
        file_path = tmp_path / "test.txt"
        file_path.write_text("test content")

        result = read_secure_file(file_path)

        assert result == "test content"

    def test_read_secure_file_strips_content(self, tmp_path: Path) -> None:
        """Test read_secure_file strips whitespace."""
        file_path = tmp_path / "test.txt"
        file_path.write_text("  content  \n")

        result = read_secure_file(file_path)

        assert result == "content"

    def test_read_secure_file_returns_none_for_missing(self, tmp_path: Path) -> None:
        """Test read_secure_file returns None for missing file."""
        file_path = tmp_path / "nonexistent.txt"

        result = read_secure_file(file_path)

        assert result is None

    def test_read_secure_file_returns_none_on_error(self, tmp_path: Path) -> None:
        """Test read_secure_file returns None on read error."""
        file_path = tmp_path / "test.txt"
        file_path.write_text("content")

        with patch("builtins.open", side_effect=OSError("Read error")):
            result = read_secure_file(file_path)

        assert result is None


class TestDomainPattern:
    """Tests for DOMAIN_PATTERN regex."""

    def test_matches_valid_domains(self) -> None:
        """Test pattern matches valid domains."""
        assert DOMAIN_PATTERN.match("example.com") is not None
        assert DOMAIN_PATTERN.match("sub.example.com") is not None
        assert DOMAIN_PATTERN.match("a.b.c.d.example.com") is not None

    def test_rejects_invalid_domains(self) -> None:
        """Test pattern rejects invalid domains."""
        assert DOMAIN_PATTERN.match("-invalid.com") is None
        assert DOMAIN_PATTERN.match("invalid-.com") is None


class TestTimePattern:
    """Tests for TIME_PATTERN regex."""

    def test_matches_valid_times(self) -> None:
        """Test pattern matches valid times."""
        assert TIME_PATTERN.match("00:00") is not None
        assert TIME_PATTERN.match("23:59") is not None
        assert TIME_PATTERN.match("12:30") is not None

    def test_rejects_invalid_times(self) -> None:
        """Test pattern rejects invalid times."""
        assert TIME_PATTERN.match("24:00") is None
        assert TIME_PATTERN.match("12:60") is None


class TestUrlPattern:
    """Tests for URL_PATTERN regex."""

    def test_matches_http_urls(self) -> None:
        """Test pattern matches HTTP URLs."""
        assert URL_PATTERN.match("http://example.com") is not None

    def test_matches_https_urls(self) -> None:
        """Test pattern matches HTTPS URLs."""
        assert URL_PATTERN.match("https://example.com") is not None

    def test_matches_urls_with_port(self) -> None:
        """Test pattern matches URLs with port."""
        match = URL_PATTERN.match("https://example.com:8080")
        assert match is not None
        assert match.group(1) == "8080"

    def test_matches_urls_with_path(self) -> None:
        """Test pattern matches URLs with path."""
        assert URL_PATTERN.match("https://example.com/path/file.json") is not None
