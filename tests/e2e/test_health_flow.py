"""E2E tests for the health command.

Tests the complete health check including:
- Configuration validation
- Domains.json loading
- API connectivity
- Log directory accessibility
- Remote cache status (informational)
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
    add_denylist_mock,
)


class TestHealthBasic:
    """Tests for basic health command functionality."""

    @responses.activate
    def test_health_passes_with_valid_config(
        self,
        runner: CliRunner,
        tmp_path: Path,
    ) -> None:
        """Test that health command passes with valid configuration."""
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
            "blocklist": [
                {"domain": "youtube.com", "schedule": None},
            ]
        }
        (config_dir / "config.json").write_text(json.dumps(domains_data))

        add_denylist_mock(responses, domains=[])

        with patch("nextdns_blocker.common.get_log_dir", return_value=log_dir):
            with patch("nextdns_blocker.cli.get_log_dir", return_value=log_dir):
                result = runner.invoke(
                    main,
                    ["health", "--config-dir", str(config_dir)],
                )

        assert result.exit_code == 0
        assert "HEALTHY" in result.output
        assert "Configuration loaded" in result.output
        assert "Domains loaded" in result.output
        assert "API connectivity" in result.output

    @responses.activate
    def test_health_shows_domain_count(
        self,
        runner: CliRunner,
        tmp_path: Path,
    ) -> None:
        """Test that health command shows domain counts."""
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
            "blocklist": [
                {"domain": "youtube.com", "schedule": None},
                {"domain": "twitter.com", "schedule": None},
                {"domain": "facebook.com", "schedule": None},
            ],
            "allowlist": [
                {"domain": "trusted.com"},
            ],
        }
        (config_dir / "config.json").write_text(json.dumps(domains_data))

        add_denylist_mock(responses, domains=[])

        with patch("nextdns_blocker.common.get_log_dir", return_value=log_dir):
            with patch("nextdns_blocker.cli.get_log_dir", return_value=log_dir):
                result = runner.invoke(
                    main,
                    ["health", "--config-dir", str(config_dir)],
                )

        assert result.exit_code == 0
        assert "3 domains" in result.output
        assert "1 allowlist" in result.output


class TestHealthConfigErrors:
    """Tests for health command with configuration errors."""

    def test_health_fails_without_config(
        self,
        runner: CliRunner,
        tmp_path: Path,
    ) -> None:
        """Test that health fails when config directory doesn't exist."""
        config_dir = tmp_path / "nonexistent"

        result = runner.invoke(
            main,
            ["health", "--config-dir", str(config_dir)],
        )

        # Click should validate the path
        assert result.exit_code != 0

    def test_health_fails_without_env_file(
        self,
        runner: CliRunner,
        tmp_path: Path,
    ) -> None:
        """Test that health fails when .env file is missing."""
        config_dir = tmp_path / "config"
        config_dir.mkdir(parents=True)

        # No .env file created
        domains_data = {"blocklist": []}
        (config_dir / "config.json").write_text(json.dumps(domains_data))

        result = runner.invoke(
            main,
            ["health", "--config-dir", str(config_dir)],
        )

        assert result.exit_code != 0
        assert "Configuration" in result.output or "Config" in result.output

    def test_health_fails_without_domains_json(
        self,
        runner: CliRunner,
        tmp_path: Path,
    ) -> None:
        """Test that health fails when config.json is missing."""
        config_dir = tmp_path / "config"
        config_dir.mkdir(parents=True)

        (config_dir / ".env").write_text(
            f"NEXTDNS_API_KEY={TEST_API_KEY}\n"
            f"NEXTDNS_PROFILE_ID={TEST_PROFILE_ID}\n"
            f"TIMEZONE={TEST_TIMEZONE}\n"
        )

        # No config.json file created

        result = runner.invoke(
            main,
            ["health", "--config-dir", str(config_dir)],
        )

        assert result.exit_code != 0


class TestHealthAPIConnectivity:
    """Tests for health command API connectivity checks."""

    @responses.activate
    def test_health_reports_api_failure(
        self,
        runner: CliRunner,
        tmp_path: Path,
    ) -> None:
        """Test that health reports API connectivity failure."""
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

        # API returns error
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
                    ["health", "--config-dir", str(config_dir)],
                )

        # Should show degraded status due to API failure
        assert "DEGRADED" in result.output or "failed" in result.output.lower()

    @responses.activate
    def test_health_shows_denylist_count(
        self,
        runner: CliRunner,
        tmp_path: Path,
    ) -> None:
        """Test that health shows items in denylist from API."""
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

        # API returns 5 blocked domains
        add_denylist_mock(
            responses,
            domains=["a.com", "b.com", "c.com", "d.com", "e.com"],
        )

        with patch("nextdns_blocker.common.get_log_dir", return_value=log_dir):
            with patch("nextdns_blocker.cli.get_log_dir", return_value=log_dir):
                result = runner.invoke(
                    main,
                    ["health", "--config-dir", str(config_dir)],
                )

        assert result.exit_code == 0
        assert "5 items in denylist" in result.output


class TestHealthLogDirectory:
    """Tests for health command log directory checks."""

    @responses.activate
    def test_health_shows_log_directory(
        self,
        runner: CliRunner,
        tmp_path: Path,
    ) -> None:
        """Test that health shows log directory path."""
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

        add_denylist_mock(responses, domains=[])

        with patch("nextdns_blocker.common.get_log_dir", return_value=log_dir):
            with patch("nextdns_blocker.cli.get_log_dir", return_value=log_dir):
                with patch("nextdns_blocker.cli.ensure_log_dir"):
                    result = runner.invoke(
                        main,
                        ["health", "--config-dir", str(config_dir)],
                    )

        assert result.exit_code == 0
        assert "Log directory" in result.output


class TestHealthSummary:
    """Tests for health command summary output."""

    @responses.activate
    def test_health_shows_check_counts(
        self,
        runner: CliRunner,
        tmp_path: Path,
    ) -> None:
        """Test that health shows pass/total check counts."""
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

        add_denylist_mock(responses, domains=[])

        with patch("nextdns_blocker.common.get_log_dir", return_value=log_dir):
            with patch("nextdns_blocker.cli.get_log_dir", return_value=log_dir):
                result = runner.invoke(
                    main,
                    ["health", "--config-dir", str(config_dir)],
                )

        assert result.exit_code == 0
        # Should show something like "4/4 checks passed"
        assert "checks passed" in result.output.lower()
