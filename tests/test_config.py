"""Tests for config module functions."""

from pathlib import Path
from unittest.mock import patch

import pytest

from nextdns_blocker.config import (
    DEFAULT_RETRIES,
    DEFAULT_TIMEOUT,
    DEFAULT_TIMEZONE,
    get_config_dir,
    get_data_dir,
    parse_duration,
    parse_unblock_delay_seconds,
    resolve_schedule_reference,
    validate_allowlist_config,
    validate_api_key,
    validate_category_config,
    validate_discord_webhook,
    validate_domain_config,
    validate_nextdns_category,
    validate_nextdns_service,
    validate_no_duplicate_domains,
    validate_no_duplicates,
    validate_profile_id,
    validate_schedule,
    validate_schedule_name,
    validate_schedule_or_reference,
    validate_schedules_section,
    validate_slack_webhook,
    validate_telegram_bot_token,
    validate_unblock_delay,
    validate_unique_category_ids,
)
from nextdns_blocker.exceptions import ConfigurationError


class TestParseDuration:
    """Tests for parse_duration function."""

    def test_never(self):
        """Test 'never' returns None."""
        assert parse_duration("never") is None
        assert parse_duration("NEVER") is None

    def test_zero(self):
        """Test '0' returns 0."""
        assert parse_duration("0") == 0

    def test_minutes(self):
        """Test minute durations."""
        assert parse_duration("30m") == 30 * 60
        assert parse_duration("1m") == 60
        assert parse_duration("90m") == 90 * 60

    def test_hours(self):
        """Test hour durations."""
        assert parse_duration("1h") == 3600
        assert parse_duration("2h") == 7200
        assert parse_duration("24h") == 86400

    def test_days(self):
        """Test day durations."""
        assert parse_duration("1d") == 86400
        assert parse_duration("7d") == 7 * 86400

    def test_zero_with_unit(self):
        """Test '0' amount with unit returns 0."""
        assert parse_duration("0m") == 0
        assert parse_duration("0h") == 0
        assert parse_duration("0d") == 0

    def test_invalid_format(self):
        """Test invalid formats raise ValueError."""
        with pytest.raises(ValueError):
            parse_duration("invalid")
        with pytest.raises(ValueError):
            parse_duration("30")
        with pytest.raises(ValueError):
            parse_duration("30x")
        with pytest.raises(ValueError):
            parse_duration("")
        with pytest.raises(ValueError):
            parse_duration(None)

    def test_whitespace_handling(self):
        """Test whitespace is stripped."""
        assert parse_duration("  30m  ") == 30 * 60
        assert parse_duration("  never  ") is None


class TestValidateApiKey:
    """Tests for validate_api_key function."""

    def test_valid_api_key(self):
        """Test valid API keys."""
        assert validate_api_key("abcdefgh12345678") is True
        assert validate_api_key("test_api_key_12345") is True
        assert validate_api_key("API-KEY-123") is True

    def test_invalid_api_key(self):
        """Test invalid API keys."""
        assert validate_api_key("") is False
        assert validate_api_key("short") is False  # Less than 8 chars
        assert validate_api_key("abc123!") is False  # Invalid character
        assert validate_api_key(None) is False
        assert validate_api_key(12345) is False


class TestValidateProfileId:
    """Tests for validate_profile_id function."""

    def test_valid_profile_id(self):
        """Test valid profile IDs."""
        assert validate_profile_id("abc123") is True
        assert validate_profile_id("test") is True
        assert validate_profile_id("profile-id-123") is True

    def test_invalid_profile_id(self):
        """Test invalid profile IDs."""
        assert validate_profile_id("") is False
        assert validate_profile_id("abc") is False  # Less than 4 chars
        assert validate_profile_id("a" * 31) is False  # More than 30 chars
        assert validate_profile_id(None) is False


class TestValidateDiscordWebhook:
    """Tests for validate_discord_webhook function."""

    def test_valid_webhook(self):
        """Test valid Discord webhook URLs."""
        valid_url = "https://discord.com/api/webhooks/12345678901234567/" + "a" * 68
        assert validate_discord_webhook(valid_url) is True

    def test_invalid_webhook(self):
        """Test invalid Discord webhook URLs."""
        assert validate_discord_webhook("") is False
        assert validate_discord_webhook("https://example.com") is False
        assert validate_discord_webhook("https://discord.com/api/webhooks/123/short") is False
        assert validate_discord_webhook(None) is False


class TestValidateTelegramBotToken:
    """Tests for validate_telegram_bot_token function."""

    def test_valid_token(self):
        """Test valid Telegram bot tokens."""
        valid_token = "123456789:" + "a" * 35
        assert validate_telegram_bot_token(valid_token) is True

    def test_invalid_token(self):
        """Test invalid Telegram bot tokens."""
        assert validate_telegram_bot_token("") is False
        assert validate_telegram_bot_token("invalid") is False
        assert validate_telegram_bot_token("123:short") is False
        assert validate_telegram_bot_token(None) is False


class TestValidateSlackWebhook:
    """Tests for validate_slack_webhook function."""

    def test_valid_webhook(self):
        """Test valid Slack webhook URLs."""
        valid_url = "https://hooks.slack.com/services/T00000000/B00000000/XXXXXXXX"
        assert validate_slack_webhook(valid_url) is True

    def test_invalid_webhook(self):
        """Test invalid Slack webhook URLs."""
        assert validate_slack_webhook("") is False
        assert validate_slack_webhook("https://example.com") is False
        assert validate_slack_webhook(None) is False


class TestValidateUnblockDelay:
    """Tests for validate_unblock_delay function."""

    def test_valid_delays(self):
        """Test valid unblock delay values."""
        assert validate_unblock_delay("never") is True
        assert validate_unblock_delay("0") is True
        assert validate_unblock_delay("30m") is True
        assert validate_unblock_delay("2h") is True
        assert validate_unblock_delay("1d") is True

    def test_invalid_delays(self):
        """Test invalid unblock delay values."""
        assert validate_unblock_delay("") is False
        assert validate_unblock_delay("invalid") is False
        assert validate_unblock_delay(None) is False


class TestParseUnblockDelaySeconds:
    """Tests for parse_unblock_delay_seconds function."""

    def test_parse_values(self):
        """Test parsing unblock delay values to seconds."""
        assert parse_unblock_delay_seconds("never") is None
        assert parse_unblock_delay_seconds("0") == 0
        assert parse_unblock_delay_seconds("30m") == 1800
        assert parse_unblock_delay_seconds("2h") == 7200
        assert parse_unblock_delay_seconds("1d") == 86400


class TestGetConfigDir:
    """Tests for get_config_dir function."""

    def test_override_path(self, temp_dir):
        """Test that override path is used when provided."""
        result = get_config_dir(temp_dir)
        assert result == temp_dir.resolve()

    def test_cwd_with_env_file(self, temp_dir):
        """Test that CWD is used if .env exists."""
        env_file = temp_dir / ".env"
        env_file.write_text("TEST=value")

        with patch("nextdns_blocker.config.Path.cwd") as mock_cwd:
            mock_cwd.return_value = temp_dir
            result = get_config_dir()
            assert result == temp_dir

    def test_invalid_override_outside_home(self):
        """Test that override outside allowed directories raises error."""
        with pytest.raises(ConfigurationError):
            get_config_dir(Path("/etc/passwd"))


class TestGetDataDir:
    """Tests for get_data_dir function."""

    def test_returns_path(self):
        """Test that get_data_dir returns a Path."""
        result = get_data_dir()
        assert isinstance(result, Path)


class TestValidateSchedule:
    """Tests for validate_schedule function."""

    def test_valid_schedule(self):
        """Test valid schedule configuration."""
        schedule = {
            "available_hours": [
                {
                    "days": ["monday", "tuesday"],
                    "time_ranges": [{"start": "09:00", "end": "17:00"}],
                }
            ]
        }
        errors = validate_schedule(schedule, "test")
        assert errors == []

    def test_valid_blocked_hours(self):
        """Test valid blocked_hours schedule."""
        schedule = {
            "blocked_hours": [
                {
                    "days": ["saturday", "sunday"],
                    "time_ranges": [{"start": "00:00", "end": "12:00"}],
                }
            ]
        }
        errors = validate_schedule(schedule, "test")
        assert errors == []

    def test_both_hours_types_invalid(self):
        """Test that having both available_hours and blocked_hours is invalid."""
        schedule = {
            "available_hours": [],
            "blocked_hours": [],
        }
        errors = validate_schedule(schedule, "test")
        assert len(errors) == 1
        assert "both" in errors[0].lower()

    def test_invalid_schedule_type(self):
        """Test that non-dict schedule is invalid."""
        errors = validate_schedule("invalid", "test")
        assert len(errors) == 1
        assert "dictionary" in errors[0].lower()

    def test_empty_schedule_valid(self):
        """Test that empty schedule (no hours) is valid."""
        errors = validate_schedule({}, "test")
        assert errors == []

    def test_invalid_day(self):
        """Test invalid day name."""
        schedule = {
            "available_hours": [
                {
                    "days": ["invalid_day"],
                    "time_ranges": [{"start": "09:00", "end": "17:00"}],
                }
            ]
        }
        errors = validate_schedule(schedule, "test")
        assert any("invalid day" in e.lower() for e in errors)

    def test_invalid_time_format(self):
        """Test invalid time format."""
        schedule = {
            "available_hours": [
                {
                    "days": ["monday"],
                    "time_ranges": [{"start": "25:00", "end": "17:00"}],
                }
            ]
        }
        errors = validate_schedule(schedule, "test")
        assert any("invalid time format" in e.lower() for e in errors)

    def test_missing_time_key(self):
        """Test missing start or end key."""
        schedule = {
            "available_hours": [
                {
                    "days": ["monday"],
                    "time_ranges": [{"start": "09:00"}],  # Missing 'end'
                }
            ]
        }
        errors = validate_schedule(schedule, "test")
        assert any("missing" in e.lower() for e in errors)

    def test_non_list_hours(self):
        """Test that non-list hours value is invalid."""
        schedule = {"available_hours": "not a list"}
        errors = validate_schedule(schedule, "test")
        assert any("must be a list" in e.lower() for e in errors)

    def test_non_dict_block(self):
        """Test that non-dict hour block is invalid."""
        schedule = {"available_hours": ["not a dict"]}
        errors = validate_schedule(schedule, "test")
        assert any("must be a dictionary" in e.lower() for e in errors)

    def test_non_dict_time_range(self):
        """Test that non-dict time_range is invalid."""
        schedule = {
            "available_hours": [
                {
                    "days": ["monday"],
                    "time_ranges": ["not a dict"],
                }
            ]
        }
        errors = validate_schedule(schedule, "test")
        assert any("must be a dictionary" in e.lower() for e in errors)


class TestValidateScheduleName:
    """Tests for validate_schedule_name function."""

    def test_valid_names(self):
        """Test valid schedule names."""
        assert validate_schedule_name("workdays") is True
        assert validate_schedule_name("work-hours") is True
        assert validate_schedule_name("schedule1") is True

    def test_invalid_names(self):
        """Test invalid schedule names."""
        assert validate_schedule_name("") is False
        assert validate_schedule_name("1schedule") is False  # Starts with number
        assert validate_schedule_name("-schedule") is False  # Starts with hyphen
        assert validate_schedule_name("Schedule") is False  # Uppercase
        assert validate_schedule_name("a" * 51) is False  # Too long
        assert validate_schedule_name(None) is False


class TestValidateSchedulesSection:
    """Tests for validate_schedules_section function."""

    def test_valid_schedules(self):
        """Test valid schedules section."""
        schedules = {
            "workdays": {
                "available_hours": [
                    {
                        "days": ["monday", "friday"],
                        "time_ranges": [{"start": "09:00", "end": "17:00"}],
                    }
                ]
            }
        }
        errors = validate_schedules_section(schedules)
        assert errors == []

    def test_invalid_schedule_name(self):
        """Test invalid schedule name in section."""
        schedules = {"Invalid-Name": {"available_hours": []}}
        errors = validate_schedules_section(schedules)
        assert any("invalid name" in e.lower() for e in errors)

    def test_non_dict_schedules(self):
        """Test that non-dict schedules section is invalid."""
        errors = validate_schedules_section("not a dict")
        assert any("must be an object" in e.lower() for e in errors)


class TestValidateScheduleOrReference:
    """Tests for validate_schedule_or_reference function."""

    def test_valid_reference(self):
        """Test valid schedule reference."""
        valid_names = {"workdays", "weekends"}
        errors = validate_schedule_or_reference("workdays", "test", valid_names)
        assert errors == []

    def test_invalid_reference(self):
        """Test invalid schedule reference."""
        valid_names = {"workdays"}
        errors = validate_schedule_or_reference("unknown", "test", valid_names)
        assert any("unknown schedule" in e.lower() for e in errors)

    def test_inline_schedule(self):
        """Test inline schedule validation."""
        schedule = {
            "available_hours": [
                {
                    "days": ["monday"],
                    "time_ranges": [{"start": "09:00", "end": "17:00"}],
                }
            ]
        }
        errors = validate_schedule_or_reference(schedule, "test", set())
        assert errors == []

    def test_none_schedule(self):
        """Test that None schedule is valid."""
        errors = validate_schedule_or_reference(None, "test", set())
        assert errors == []

    def test_invalid_type(self):
        """Test that invalid type returns error."""
        errors = validate_schedule_or_reference(123, "test", set())
        assert any("must be a string" in e.lower() for e in errors)


class TestResolveScheduleReference:
    """Tests for resolve_schedule_reference function."""

    def test_resolve_reference(self):
        """Test resolving schedule reference."""
        schedules = {"workdays": {"available_hours": [{"days": ["monday"], "time_ranges": []}]}}
        result = resolve_schedule_reference("workdays", schedules)
        assert result is not None
        assert "available_hours" in result

    def test_resolve_none(self):
        """Test that None returns None."""
        result = resolve_schedule_reference(None, {})
        assert result is None

    def test_resolve_inline(self):
        """Test that inline schedule is returned as-is."""
        inline = {"available_hours": []}
        result = resolve_schedule_reference(inline, {})
        assert result == inline

    def test_resolve_unknown_reference(self):
        """Test that unknown reference returns None."""
        result = resolve_schedule_reference("unknown", {})
        assert result is None

    def test_resolve_invalid_type(self):
        """Test that invalid type returns None."""
        result = resolve_schedule_reference(123, {})
        assert result is None


class TestValidateDomainConfig:
    """Tests for validate_domain_config function."""

    def test_valid_config(self):
        """Test valid domain config."""
        config = {
            "domain": "example.com",
            "schedule": None,
        }
        errors = validate_domain_config(config, 0)
        assert errors == []

    def test_missing_domain(self):
        """Test missing domain field."""
        config = {"schedule": None}
        errors = validate_domain_config(config, 0)
        assert any("missing" in e.lower() for e in errors)

    def test_empty_domain(self):
        """Test empty domain field."""
        config = {"domain": ""}
        errors = validate_domain_config(config, 0)
        assert any("empty" in e.lower() for e in errors)

    def test_invalid_domain(self):
        """Test invalid domain format."""
        config = {"domain": "invalid domain"}
        errors = validate_domain_config(config, 0)
        assert any("invalid domain" in e.lower() for e in errors)

    def test_invalid_unblock_delay(self):
        """Test invalid unblock_delay."""
        config = {
            "domain": "example.com",
            "unblock_delay": "invalid",
        }
        errors = validate_domain_config(config, 0)
        assert any("unblock_delay" in e.lower() for e in errors)

    def test_valid_unblock_delay(self):
        """Test valid unblock_delay."""
        config = {
            "domain": "example.com",
            "unblock_delay": "30m",
        }
        errors = validate_domain_config(config, 0)
        assert errors == []


class TestValidateAllowlistConfig:
    """Tests for validate_allowlist_config function."""

    def test_valid_allowlist(self):
        """Test valid allowlist config."""
        config = {"domain": "example.com"}
        errors = validate_allowlist_config(config, 0)
        assert errors == []

    def test_missing_domain(self):
        """Test missing domain in allowlist."""
        config = {}
        errors = validate_allowlist_config(config, 0)
        assert any("missing" in e.lower() for e in errors)

    def test_invalid_suppress_warning(self):
        """Test invalid suppress_subdomain_warning type."""
        config = {
            "domain": "example.com",
            "suppress_subdomain_warning": "not a bool",
        }
        errors = validate_allowlist_config(config, 0)
        assert any("boolean" in e.lower() for e in errors)

    def test_valid_suppress_warning(self):
        """Test valid suppress_subdomain_warning."""
        config = {
            "domain": "example.com",
            "suppress_subdomain_warning": True,
        }
        errors = validate_allowlist_config(config, 0)
        assert errors == []


class TestValidateCategoryConfig:
    """Tests for validate_category_config function."""

    def test_missing_id(self):
        """Test missing id field."""
        config = {"schedule": None}
        errors = validate_category_config(config, 0)
        assert any("missing" in e.lower() for e in errors)


class TestDefaults:
    """Tests for default values."""

    def test_default_values(self):
        """Test default configuration values."""
        assert DEFAULT_TIMEOUT == 10
        assert DEFAULT_RETRIES == 3
        assert DEFAULT_TIMEZONE == "UTC"


class TestValidateNextdnsCategory:
    """Tests for validate_nextdns_category function."""

    def test_valid_category(self):
        """Test valid NextDNS category."""

        config = {"id": "porn"}
        errors = validate_nextdns_category(config, 0)
        assert errors == []

    def test_missing_id(self):
        """Test missing id field."""

        config = {}
        errors = validate_nextdns_category(config, 0)
        assert any("missing" in e.lower() for e in errors)

    def test_invalid_category_id(self):
        """Test invalid category ID."""

        config = {"id": "invalid-category"}
        errors = validate_nextdns_category(config, 0)
        assert any("invalid category" in e.lower() for e in errors)

    def test_empty_id(self):
        """Test empty id."""

        config = {"id": ""}
        errors = validate_nextdns_category(config, 0)
        assert any("empty" in e.lower() for e in errors)


class TestValidateNextdnsService:
    """Tests for validate_nextdns_service function."""

    def test_valid_service(self):
        """Test valid NextDNS service."""

        config = {"id": "youtube"}
        errors = validate_nextdns_service(config, 0)
        assert errors == []

    def test_missing_id(self):
        """Test missing id field."""

        config = {}
        errors = validate_nextdns_service(config, 0)
        assert any("missing" in e.lower() for e in errors)

    def test_invalid_service_id(self):
        """Test invalid service ID."""

        config = {"id": "invalid-service"}
        errors = validate_nextdns_service(config, 0)
        assert any("invalid service" in e.lower() for e in errors)

    def test_empty_id(self):
        """Test empty id."""

        config = {"id": ""}
        errors = validate_nextdns_service(config, 0)
        assert any("empty" in e.lower() for e in errors)


class TestValidateNoDuplicateDomains:
    """Tests for validate_no_duplicate_domains function."""

    def test_no_duplicates(self):
        """Test categories and blocklist with no shared domains."""
        categories = [{"id": "cat1", "domains": ["a.com"]}]
        blocklist = [{"domain": "b.com"}]
        errors = validate_no_duplicate_domains(categories, blocklist)
        assert errors == []

    def test_with_duplicates_between_category_and_blocklist(self):
        """Test domain in both category and blocklist."""
        categories = [{"id": "cat1", "domains": ["a.com"]}]
        blocklist = [{"domain": "a.com"}]
        errors = validate_no_duplicate_domains(categories, blocklist)
        assert any("multiple locations" in e.lower() for e in errors)

    def test_with_duplicates_across_categories(self):
        """Test domain in multiple categories."""
        categories = [
            {"id": "cat1", "domains": ["a.com"]},
            {"id": "cat2", "domains": ["a.com"]},
        ]
        blocklist = []
        errors = validate_no_duplicate_domains(categories, blocklist)
        assert any("multiple locations" in e.lower() for e in errors)


class TestValidateNoDuplicates:
    """Tests for validate_no_duplicates function."""

    def test_no_duplicates(self):
        """Test list with no duplicates."""
        entries = [{"domain": "a.com"}, {"domain": "b.com"}]
        errors = validate_no_duplicates(entries, "blocklist")
        assert errors == []

    def test_with_duplicates(self):
        """Test list with duplicate domains."""
        entries = [{"domain": "a.com"}, {"domain": "A.COM"}]
        errors = validate_no_duplicates(entries, "blocklist")
        assert any("duplicate" in e.lower() for e in errors)

    def test_empty_domain_skipped(self):
        """Test that empty domains are skipped."""
        entries = [{"domain": ""}, {"domain": "a.com"}]
        errors = validate_no_duplicates(entries, "blocklist")
        assert errors == []


class TestValidateUniqueCategoryIds:
    """Tests for validate_unique_category_ids function."""

    def test_no_duplicates(self):
        """Test list with no duplicate IDs."""

        categories = [{"id": "cat1"}, {"id": "cat2"}]
        errors = validate_unique_category_ids(categories)
        assert errors == []

    def test_with_duplicates(self):
        """Test list with duplicate IDs."""

        categories = [{"id": "cat1"}, {"id": "CAT1"}]
        errors = validate_unique_category_ids(categories)
        assert any("duplicate" in e.lower() for e in errors)
