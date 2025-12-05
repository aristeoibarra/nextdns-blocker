"""Tests for configuration validation."""

from nextdns_blocker.common import validate_domain, validate_time_format
from nextdns_blocker.config import validate_domain_config


class TestValidateDomainConfig:
    """Tests for validate_domain_config function."""

    def test_valid_config(self, sample_domain_config):
        errors = validate_domain_config(sample_domain_config, 0)
        assert errors == []

    def test_valid_config_no_schedule(self):
        config = {"domain": "example.com"}
        errors = validate_domain_config(config, 0)
        assert errors == []

    def test_valid_config_null_schedule(self, always_blocked_config):
        errors = validate_domain_config(always_blocked_config, 0)
        assert errors == []

    def test_missing_domain(self):
        config = {"description": "No domain"}
        errors = validate_domain_config(config, 0)
        assert len(errors) == 1
        assert "Missing" in errors[0] and "domain" in errors[0]

    def test_empty_domain(self):
        config = {"domain": ""}
        errors = validate_domain_config(config, 0)
        assert len(errors) == 1
        assert "Empty" in errors[0] or "invalid" in errors[0]

    def test_whitespace_domain(self):
        config = {"domain": "   "}
        errors = validate_domain_config(config, 0)
        assert len(errors) == 1
        assert "Empty" in errors[0] or "invalid" in errors[0]

    def test_invalid_schedule_type(self):
        config = {"domain": "example.com", "schedule": "invalid"}
        errors = validate_domain_config(config, 0)
        assert len(errors) == 1
        assert "schedule must be" in errors[0]

    def test_invalid_available_hours_type(self):
        config = {"domain": "example.com", "schedule": {"available_hours": "invalid"}}
        errors = validate_domain_config(config, 0)
        assert len(errors) == 1
        assert "available_hours must be" in errors[0]

    def test_invalid_day_name(self):
        config = {
            "domain": "example.com",
            "schedule": {"available_hours": [{"days": ["invalid_day"], "time_ranges": []}]},
        }
        errors = validate_domain_config(config, 0)
        assert len(errors) == 1
        assert "invalid day" in errors[0]

    def test_missing_time_range_start(self):
        config = {
            "domain": "example.com",
            "schedule": {
                "available_hours": [{"days": ["monday"], "time_ranges": [{"end": "17:00"}]}]
            },
        }
        errors = validate_domain_config(config, 0)
        assert len(errors) == 1
        assert "missing 'start'" in errors[0]

    def test_missing_time_range_end(self):
        config = {
            "domain": "example.com",
            "schedule": {
                "available_hours": [{"days": ["monday"], "time_ranges": [{"start": "09:00"}]}]
            },
        }
        errors = validate_domain_config(config, 0)
        assert len(errors) == 1
        assert "missing 'end'" in errors[0]

    def test_multiple_errors(self):
        config = {
            "domain": "example.com",
            "schedule": {
                "available_hours": [
                    {
                        "days": ["invalid_day", "another_bad"],
                        "time_ranges": [{"start": "09:00"}],  # missing end
                    }
                ]
            },
        }
        errors = validate_domain_config(config, 0)
        assert len(errors) == 3  # 2 invalid days + 1 missing end

    def test_case_insensitive_days(self):
        config = {
            "domain": "example.com",
            "schedule": {
                "available_hours": [
                    {
                        "days": ["Monday", "TUESDAY"],
                        "time_ranges": [{"start": "09:00", "end": "17:00"}],
                    }
                ]
            },
        }
        errors = validate_domain_config(config, 0)
        assert errors == []

    def test_empty_schedule_dict(self):
        config = {"domain": "example.com", "schedule": {}}
        errors = validate_domain_config(config, 0)
        assert errors == []

    def test_invalid_time_format_start(self):
        """Should reject invalid time format in start field."""
        config = {
            "domain": "example.com",
            "schedule": {
                "available_hours": [
                    {"days": ["monday"], "time_ranges": [{"start": "9am", "end": "17:00"}]}
                ]
            },
        }
        errors = validate_domain_config(config, 0)
        assert len(errors) == 1
        assert "invalid time format" in errors[0]
        assert "start" in errors[0]

    def test_invalid_time_format_end(self):
        """Should reject invalid time format in end field."""
        config = {
            "domain": "example.com",
            "schedule": {
                "available_hours": [
                    {"days": ["monday"], "time_ranges": [{"start": "09:00", "end": "5pm"}]}
                ]
            },
        }
        errors = validate_domain_config(config, 0)
        assert len(errors) == 1
        assert "invalid time format" in errors[0]
        assert "end" in errors[0]

    def test_invalid_time_format_both(self):
        """Should reject invalid time format in both fields."""
        config = {
            "domain": "example.com",
            "schedule": {
                "available_hours": [
                    {"days": ["monday"], "time_ranges": [{"start": "9am", "end": "5pm"}]}
                ]
            },
        }
        errors = validate_domain_config(config, 0)
        assert len(errors) == 2


class TestValidateTimeFormat:
    """Tests for validate_time_format function."""

    def test_valid_time_00_00(self):
        assert validate_time_format("00:00") is True

    def test_valid_time_23_59(self):
        assert validate_time_format("23:59") is True

    def test_valid_time_09_30(self):
        assert validate_time_format("09:30") is True

    def test_valid_time_single_digit_hour(self):
        """Should accept single digit hour like 9:00."""
        assert validate_time_format("9:00") is True

    def test_invalid_time_24_00(self):
        """Should reject 24:00."""
        assert validate_time_format("24:00") is False

    def test_invalid_time_12_60(self):
        """Should reject invalid minutes."""
        assert validate_time_format("12:60") is False

    def test_invalid_time_am_pm(self):
        """Should reject AM/PM format."""
        assert validate_time_format("9:00 AM") is False

    def test_invalid_time_empty(self):
        assert validate_time_format("") is False

    def test_invalid_time_none(self):
        assert validate_time_format(None) is False

    def test_invalid_time_no_colon(self):
        assert validate_time_format("0900") is False

    def test_invalid_time_letters(self):
        assert validate_time_format("ab:cd") is False


class TestValidateDomainTrailingDot:
    """Tests for domain validation rejecting trailing dots."""

    def test_domain_with_trailing_dot_rejected(self):
        """Should reject domain with trailing dot."""
        assert validate_domain("example.com.") is False

    def test_domain_without_trailing_dot_accepted(self):
        """Should accept domain without trailing dot."""
        assert validate_domain("example.com") is True

    def test_subdomain_with_trailing_dot_rejected(self):
        """Should reject subdomain with trailing dot."""
        assert validate_domain("sub.example.com.") is False

    def test_just_dot_rejected(self):
        """Should reject just a dot."""
        assert validate_domain(".") is False
