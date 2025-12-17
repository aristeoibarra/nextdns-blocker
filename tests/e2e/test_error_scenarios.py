"""E2E tests for error scenarios.

Tests error handling across commands including:
- API failures
- Network timeouts
- Invalid configurations
- Protected domain violations
- Missing files
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import responses
from click.testing import CliRunner

from nextdns_blocker.cli import main
from nextdns_blocker.client import API_URL

from .conftest import (
    TEST_API_KEY,
    TEST_PROFILE_ID,
    TEST_TIMEZONE,
)


class TestAPIErrors:
    """Tests for API error handling."""

    @responses.activate
    def test_sync_handles_401_unauthorized(
        self,
        runner: CliRunner,
        tmp_path: Path,
    ) -> None:
        """Test that sync handles 401 Unauthorized gracefully."""
        config_dir = tmp_path / "config"
        log_dir = tmp_path / "logs"
        config_dir.mkdir(parents=True)
        log_dir.mkdir(parents=True)

        (config_dir / ".env").write_text(
            f"NEXTDNS_API_KEY=invalid-key\n"
            f"NEXTDNS_PROFILE_ID={TEST_PROFILE_ID}\n"
            f"TIMEZONE={TEST_TIMEZONE}\n"
        )

        domains_data = {"blocklist": [{"domain": "youtube.com", "schedule": None}]}
        (config_dir / "config.json").write_text(json.dumps(domains_data))

        responses.add(
            responses.GET,
            f"{API_URL}/profiles/{TEST_PROFILE_ID}/denylist",
            json={"error": "Unauthorized"},
            status=401,
        )

        with patch("nextdns_blocker.common.get_log_dir", return_value=log_dir):
            with patch("nextdns_blocker.cli.get_log_dir", return_value=log_dir):
                result = runner.invoke(
                    main,
                    ["sync", "--config-dir", str(config_dir)],
                )

        # Should handle the error gracefully
        assert result.exit_code == 0 or "error" in result.output.lower()

    @responses.activate
    def test_sync_handles_500_server_error(
        self,
        runner: CliRunner,
        tmp_path: Path,
    ) -> None:
        """Test that sync handles 500 Server Error gracefully."""
        config_dir = tmp_path / "config"
        log_dir = tmp_path / "logs"
        config_dir.mkdir(parents=True)
        log_dir.mkdir(parents=True)

        (config_dir / ".env").write_text(
            f"NEXTDNS_API_KEY={TEST_API_KEY}\n"
            f"NEXTDNS_PROFILE_ID={TEST_PROFILE_ID}\n"
            f"TIMEZONE={TEST_TIMEZONE}\n"
        )

        domains_data = {"blocklist": [{"domain": "youtube.com", "schedule": None}]}
        (config_dir / "config.json").write_text(json.dumps(domains_data))

        responses.add(
            responses.GET,
            f"{API_URL}/profiles/{TEST_PROFILE_ID}/denylist",
            json={"error": "Internal Server Error"},
            status=500,
        )

        with patch("nextdns_blocker.common.get_log_dir", return_value=log_dir):
            with patch("nextdns_blocker.cli.get_log_dir", return_value=log_dir):
                result = runner.invoke(
                    main,
                    ["sync", "--config-dir", str(config_dir)],
                )

        # Should handle the error
        assert result.exit_code == 0 or "error" in result.output.lower()

    @responses.activate
    def test_sync_handles_rate_limit(
        self,
        runner: CliRunner,
        tmp_path: Path,
    ) -> None:
        """Test that sync handles rate limiting (429) gracefully."""
        config_dir = tmp_path / "config"
        log_dir = tmp_path / "logs"
        config_dir.mkdir(parents=True)
        log_dir.mkdir(parents=True)

        (config_dir / ".env").write_text(
            f"NEXTDNS_API_KEY={TEST_API_KEY}\n"
            f"NEXTDNS_PROFILE_ID={TEST_PROFILE_ID}\n"
            f"TIMEZONE={TEST_TIMEZONE}\n"
        )

        domains_data = {"blocklist": [{"domain": "youtube.com", "schedule": None}]}
        (config_dir / "config.json").write_text(json.dumps(domains_data))

        responses.add(
            responses.GET,
            f"{API_URL}/profiles/{TEST_PROFILE_ID}/denylist",
            json={"error": "Too Many Requests"},
            status=429,
        )

        with patch("nextdns_blocker.common.get_log_dir", return_value=log_dir):
            with patch("nextdns_blocker.cli.get_log_dir", return_value=log_dir):
                result = runner.invoke(
                    main,
                    ["sync", "--config-dir", str(config_dir)],
                )

        # Should handle rate limiting
        assert result.exit_code == 0 or "error" in result.output.lower()


class TestProtectedDomainErrors:
    """Tests for protected domain error handling."""

    @responses.activate
    def test_unblock_rejects_protected_domain(
        self,
        runner: CliRunner,
        tmp_path: Path,
    ) -> None:
        """Test that unblock command rejects protected domains (unblock_delay: never)."""
        config_dir = tmp_path / "config"
        log_dir = tmp_path / "logs"
        config_dir.mkdir(parents=True)
        log_dir.mkdir(parents=True)

        (config_dir / ".env").write_text(
            f"NEXTDNS_API_KEY={TEST_API_KEY}\n"
            f"NEXTDNS_PROFILE_ID={TEST_PROFILE_ID}\n"
            f"TIMEZONE={TEST_TIMEZONE}\n"
        )

        domains_data = {
            "blocklist": [{"domain": "gambling.com", "protected": True, "schedule": None}]
        }
        (config_dir / "config.json").write_text(json.dumps(domains_data))

        with patch("nextdns_blocker.common.get_log_dir", return_value=log_dir):
            with patch("nextdns_blocker.cli.get_log_dir", return_value=log_dir):
                result = runner.invoke(
                    main,
                    ["unblock", "gambling.com", "--config-dir", str(config_dir)],
                )

        assert result.exit_code != 0
        # Now shows "unblock_delay: never" instead of "protected"
        assert "cannot be unblocked" in result.output.lower()


class TestInvalidDomainErrors:
    """Tests for invalid domain format handling."""

    def test_unblock_rejects_invalid_domain_format(
        self,
        runner: CliRunner,
        tmp_path: Path,
    ) -> None:
        """Test that unblock command rejects invalid domain format."""
        config_dir = tmp_path / "config"
        config_dir.mkdir(parents=True)

        (config_dir / ".env").write_text(
            f"NEXTDNS_API_KEY={TEST_API_KEY}\n"
            f"NEXTDNS_PROFILE_ID={TEST_PROFILE_ID}\n"
            f"TIMEZONE={TEST_TIMEZONE}\n"
        )

        domains_data = {"blocklist": [{"domain": "youtube.com", "schedule": None}]}
        (config_dir / "config.json").write_text(json.dumps(domains_data))

        result = runner.invoke(
            main,
            ["unblock", "not a valid domain!", "--config-dir", str(config_dir)],
        )

        assert result.exit_code != 0
        assert "invalid" in result.output.lower()

    def test_unblock_rejects_domain_with_protocol(
        self,
        runner: CliRunner,
        tmp_path: Path,
    ) -> None:
        """Test that unblock command rejects domain with protocol prefix."""
        config_dir = tmp_path / "config"
        config_dir.mkdir(parents=True)

        (config_dir / ".env").write_text(
            f"NEXTDNS_API_KEY={TEST_API_KEY}\n"
            f"NEXTDNS_PROFILE_ID={TEST_PROFILE_ID}\n"
            f"TIMEZONE={TEST_TIMEZONE}\n"
        )

        domains_data = {"blocklist": [{"domain": "youtube.com", "schedule": None}]}
        (config_dir / "config.json").write_text(json.dumps(domains_data))

        result = runner.invoke(
            main,
            ["unblock", "https://youtube.com", "--config-dir", str(config_dir)],
        )

        assert result.exit_code != 0
        assert "invalid" in result.output.lower()


class TestConfigurationErrors:
    """Tests for configuration error handling."""

    def test_sync_fails_without_env_file(
        self,
        runner: CliRunner,
        tmp_path: Path,
    ) -> None:
        """Test that sync fails gracefully without .env file."""
        config_dir = tmp_path / "config"
        config_dir.mkdir(parents=True)

        # Only create config.json, no .env
        domains_data = {"blocklist": []}
        (config_dir / "config.json").write_text(json.dumps(domains_data))

        result = runner.invoke(
            main,
            ["sync", "--config-dir", str(config_dir)],
        )

        assert result.exit_code != 0
        assert "config" in result.output.lower() or "error" in result.output.lower()

    def test_sync_fails_without_domains_file(
        self,
        runner: CliRunner,
        tmp_path: Path,
    ) -> None:
        """Test that sync fails gracefully without config.json file."""
        config_dir = tmp_path / "config"
        config_dir.mkdir(parents=True)

        # Only create .env, no config.json
        (config_dir / ".env").write_text(
            f"NEXTDNS_API_KEY={TEST_API_KEY}\n"
            f"NEXTDNS_PROFILE_ID={TEST_PROFILE_ID}\n"
            f"TIMEZONE={TEST_TIMEZONE}\n"
        )

        result = runner.invoke(
            main,
            ["sync", "--config-dir", str(config_dir)],
        )

        assert result.exit_code != 0
        assert "config" in result.output.lower() or "error" in result.output.lower()

    def test_sync_fails_with_invalid_timezone(
        self,
        runner: CliRunner,
        tmp_path: Path,
    ) -> None:
        """Test that sync handles invalid timezone gracefully."""
        config_dir = tmp_path / "config"
        log_dir = tmp_path / "logs"
        config_dir.mkdir(parents=True)
        log_dir.mkdir(parents=True)

        (config_dir / ".env").write_text(
            f"NEXTDNS_API_KEY={TEST_API_KEY}\n"
            f"NEXTDNS_PROFILE_ID={TEST_PROFILE_ID}\n"
            f"TIMEZONE=Invalid/Timezone\n"
        )

        domains_data = {"blocklist": [{"domain": "youtube.com", "schedule": None}]}
        (config_dir / "config.json").write_text(json.dumps(domains_data))

        with patch("nextdns_blocker.common.get_log_dir", return_value=log_dir):
            with patch("nextdns_blocker.cli.get_log_dir", return_value=log_dir):
                result = runner.invoke(
                    main,
                    ["sync", "--config-dir", str(config_dir)],
                )

        # Should fail or warn about invalid timezone
        assert result.exit_code != 0 or "timezone" in result.output.lower()


class TestMalformedDomainsFile:
    """Tests for malformed config.json handling."""

    def test_sync_fails_with_invalid_json(
        self,
        runner: CliRunner,
        tmp_path: Path,
    ) -> None:
        """Test that sync fails gracefully with invalid JSON in config.json."""
        config_dir = tmp_path / "config"
        config_dir.mkdir(parents=True)

        (config_dir / ".env").write_text(
            f"NEXTDNS_API_KEY={TEST_API_KEY}\n"
            f"NEXTDNS_PROFILE_ID={TEST_PROFILE_ID}\n"
            f"TIMEZONE={TEST_TIMEZONE}\n"
        )

        # Invalid JSON
        (config_dir / "config.json").write_text("{ invalid json }")

        result = runner.invoke(
            main,
            ["sync", "--config-dir", str(config_dir)],
        )

        assert result.exit_code != 0
        assert "config" in result.output.lower() or "error" in result.output.lower()

    def test_sync_fails_with_missing_domains_key(
        self,
        runner: CliRunner,
        tmp_path: Path,
    ) -> None:
        """Test that sync fails gracefully when domains key is missing."""
        config_dir = tmp_path / "config"
        config_dir.mkdir(parents=True)

        (config_dir / ".env").write_text(
            f"NEXTDNS_API_KEY={TEST_API_KEY}\n"
            f"NEXTDNS_PROFILE_ID={TEST_PROFILE_ID}\n"
            f"TIMEZONE={TEST_TIMEZONE}\n"
        )

        # Valid JSON but missing "domains" key
        (config_dir / "config.json").write_text('{"other_key": []}')

        result = runner.invoke(
            main,
            ["sync", "--config-dir", str(config_dir)],
        )

        # Should handle missing key
        assert result.exit_code != 0 or "error" in result.output.lower()


class TestVersionCommand:
    """Tests for version command."""

    def test_version_shows_version_number(
        self,
        runner: CliRunner,
    ) -> None:
        """Test that --version shows version number."""
        result = runner.invoke(main, ["--version"])

        assert result.exit_code == 0
        assert "nextdns-blocker" in result.output.lower()


class TestHelpCommand:
    """Tests for help command."""

    def test_help_shows_available_commands(
        self,
        runner: CliRunner,
    ) -> None:
        """Test that --help shows available commands."""
        result = runner.invoke(main, ["--help"])

        assert result.exit_code == 0
        assert "sync" in result.output
        assert "init" in result.output
        assert "pause" in result.output
        assert "resume" in result.output
        assert "status" in result.output
        assert "health" in result.output

    def test_sync_help_shows_options(
        self,
        runner: CliRunner,
    ) -> None:
        """Test that sync --help shows available options."""
        result = runner.invoke(main, ["sync", "--help"])

        assert result.exit_code == 0
        assert "--dry-run" in result.output
        assert "--verbose" in result.output or "-v" in result.output
        assert "--config-dir" in result.output
