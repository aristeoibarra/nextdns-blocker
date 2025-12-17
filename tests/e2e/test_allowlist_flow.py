"""E2E tests for the allow/disallow commands.

Tests the complete allowlist management including:
- Adding domains to allowlist
- Removing domains from allowlist
- Validation of domain format
- Warning when domain is blocked
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import responses
from click.testing import CliRunner

from nextdns_blocker.cli import main

from .conftest import (
    TEST_API_KEY,
    TEST_PROFILE_ID,
    TEST_TIMEZONE,
    add_allow_mock,
    add_allowlist_mock,
    add_denylist_mock,
    add_disallow_mock,
)


class TestAllowCommand:
    """Tests for the allow command."""

    @responses.activate
    def test_allow_adds_domain_to_allowlist(
        self,
        runner: CliRunner,
        tmp_path: Path,
    ) -> None:
        """Test that allow command adds a domain to allowlist."""
        config_dir = tmp_path / "config"
        log_dir = tmp_path / "logs"
        config_dir.mkdir(parents=True)
        log_dir.mkdir(parents=True)

        (config_dir / ".env").write_text(
            f"NEXTDNS_API_KEY={TEST_API_KEY}\n"
            f"NEXTDNS_PROFILE_ID={TEST_PROFILE_ID}\n"
            f"TIMEZONE={TEST_TIMEZONE}\n"
        )

        domains_data = {"blocklist": []}
        (config_dir / "config.json").write_text(json.dumps(domains_data))

        # Domain is not blocked
        add_denylist_mock(responses, domains=[])
        add_allow_mock(responses, "trusted-site.com")

        with patch("nextdns_blocker.common.get_log_dir", return_value=log_dir):
            with patch("nextdns_blocker.cli.get_log_dir", return_value=log_dir):
                result = runner.invoke(
                    main,
                    ["allow", "trusted-site.com", "--config-dir", str(config_dir)],
                )

        assert result.exit_code == 0
        assert "allowlist" in result.output.lower()
        assert "trusted-site.com" in result.output

    @responses.activate
    def test_allow_warns_when_domain_blocked(
        self,
        runner: CliRunner,
        tmp_path: Path,
    ) -> None:
        """Test that allow command warns if domain is in denylist."""
        config_dir = tmp_path / "config"
        log_dir = tmp_path / "logs"
        config_dir.mkdir(parents=True)
        log_dir.mkdir(parents=True)

        (config_dir / ".env").write_text(
            f"NEXTDNS_API_KEY={TEST_API_KEY}\n"
            f"NEXTDNS_PROFILE_ID={TEST_PROFILE_ID}\n"
            f"TIMEZONE={TEST_TIMEZONE}\n"
        )

        domains_data = {"blocklist": []}
        (config_dir / "config.json").write_text(json.dumps(domains_data))

        # Domain IS blocked
        add_denylist_mock(responses, domains=["youtube.com"])
        add_allow_mock(responses, "youtube.com")

        with patch("nextdns_blocker.common.get_log_dir", return_value=log_dir):
            with patch("nextdns_blocker.cli.get_log_dir", return_value=log_dir):
                result = runner.invoke(
                    main,
                    ["allow", "youtube.com", "--config-dir", str(config_dir)],
                )

        assert result.exit_code == 0
        assert "warning" in result.output.lower() or "blocked" in result.output.lower()

    def test_allow_rejects_invalid_domain(
        self,
        runner: CliRunner,
        tmp_path: Path,
    ) -> None:
        """Test that allow command rejects invalid domain format."""
        config_dir = tmp_path / "config"
        config_dir.mkdir(parents=True)

        (config_dir / ".env").write_text(
            f"NEXTDNS_API_KEY={TEST_API_KEY}\n"
            f"NEXTDNS_PROFILE_ID={TEST_PROFILE_ID}\n"
            f"TIMEZONE={TEST_TIMEZONE}\n"
        )

        domains_data = {"blocklist": []}
        (config_dir / "config.json").write_text(json.dumps(domains_data))

        result = runner.invoke(
            main,
            ["allow", "invalid domain with spaces", "--config-dir", str(config_dir)],
        )

        assert result.exit_code != 0
        assert "invalid" in result.output.lower()

    @responses.activate
    def test_allow_fails_on_api_error(
        self,
        runner: CliRunner,
        tmp_path: Path,
    ) -> None:
        """Test that allow command fails gracefully on API error."""
        config_dir = tmp_path / "config"
        log_dir = tmp_path / "logs"
        config_dir.mkdir(parents=True)
        log_dir.mkdir(parents=True)

        (config_dir / ".env").write_text(
            f"NEXTDNS_API_KEY={TEST_API_KEY}\n"
            f"NEXTDNS_PROFILE_ID={TEST_PROFILE_ID}\n"
            f"TIMEZONE={TEST_TIMEZONE}\n"
        )

        domains_data = {"blocklist": []}
        (config_dir / "config.json").write_text(json.dumps(domains_data))

        add_denylist_mock(responses, domains=[])
        # API returns error
        add_allow_mock(responses, "test.com", success=False)

        with patch("nextdns_blocker.common.get_log_dir", return_value=log_dir):
            with patch("nextdns_blocker.cli.get_log_dir", return_value=log_dir):
                result = runner.invoke(
                    main,
                    ["allow", "test.com", "--config-dir", str(config_dir)],
                )

        assert result.exit_code != 0
        assert "failed" in result.output.lower() or "error" in result.output.lower()


class TestDisallowCommand:
    """Tests for the disallow command."""

    @responses.activate
    def test_disallow_removes_domain_from_allowlist(
        self,
        runner: CliRunner,
        tmp_path: Path,
    ) -> None:
        """Test that disallow command removes a domain from allowlist."""
        config_dir = tmp_path / "config"
        log_dir = tmp_path / "logs"
        config_dir.mkdir(parents=True)
        log_dir.mkdir(parents=True)

        (config_dir / ".env").write_text(
            f"NEXTDNS_API_KEY={TEST_API_KEY}\n"
            f"NEXTDNS_PROFILE_ID={TEST_PROFILE_ID}\n"
            f"TIMEZONE={TEST_TIMEZONE}\n"
        )

        domains_data = {"blocklist": []}
        (config_dir / "config.json").write_text(json.dumps(domains_data))

        add_disallow_mock(responses, "trusted-site.com")

        with patch("nextdns_blocker.common.get_log_dir", return_value=log_dir):
            with patch("nextdns_blocker.cli.get_log_dir", return_value=log_dir):
                result = runner.invoke(
                    main,
                    ["disallow", "trusted-site.com", "--config-dir", str(config_dir)],
                )

        assert result.exit_code == 0
        assert "removed" in result.output.lower() or "allowlist" in result.output.lower()

    def test_disallow_rejects_invalid_domain(
        self,
        runner: CliRunner,
        tmp_path: Path,
    ) -> None:
        """Test that disallow command rejects invalid domain format."""
        config_dir = tmp_path / "config"
        config_dir.mkdir(parents=True)

        (config_dir / ".env").write_text(
            f"NEXTDNS_API_KEY={TEST_API_KEY}\n"
            f"NEXTDNS_PROFILE_ID={TEST_PROFILE_ID}\n"
            f"TIMEZONE={TEST_TIMEZONE}\n"
        )

        domains_data = {"blocklist": []}
        (config_dir / "config.json").write_text(json.dumps(domains_data))

        result = runner.invoke(
            main,
            ["disallow", "not a valid domain!", "--config-dir", str(config_dir)],
        )

        assert result.exit_code != 0
        assert "invalid" in result.output.lower()

    @responses.activate
    def test_disallow_fails_on_api_error(
        self,
        runner: CliRunner,
        tmp_path: Path,
    ) -> None:
        """Test that disallow command fails gracefully on API error."""
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

        # Mock allowlist check (client checks before DELETE)
        add_allowlist_mock(responses, domains=["test.com"])
        # API returns error for DELETE
        add_disallow_mock(responses, "test.com", success=False)

        with patch("nextdns_blocker.common.get_log_dir", return_value=log_dir):
            with patch("nextdns_blocker.cli.get_log_dir", return_value=log_dir):
                result = runner.invoke(
                    main,
                    ["disallow", "test.com", "--config-dir", str(config_dir)],
                )

        assert result.exit_code != 0
        assert "failed" in result.output.lower() or "error" in result.output.lower()


class TestAllowDisallowWorkflow:
    """Tests for complete allow → disallow workflow."""

    @responses.activate
    def test_allow_then_disallow_workflow(
        self,
        runner: CliRunner,
        tmp_path: Path,
    ) -> None:
        """Test complete workflow: allow domain → verify → disallow domain."""
        config_dir = tmp_path / "config"
        log_dir = tmp_path / "logs"
        config_dir.mkdir(parents=True)
        log_dir.mkdir(parents=True)

        (config_dir / ".env").write_text(
            f"NEXTDNS_API_KEY={TEST_API_KEY}\n"
            f"NEXTDNS_PROFILE_ID={TEST_PROFILE_ID}\n"
            f"TIMEZONE={TEST_TIMEZONE}\n"
        )

        domains_data = {"blocklist": []}
        (config_dir / "config.json").write_text(json.dumps(domains_data))

        # Step 1: Allow domain
        add_denylist_mock(responses, domains=[])
        add_allow_mock(responses, "example.com")

        with patch("nextdns_blocker.common.get_log_dir", return_value=log_dir):
            with patch("nextdns_blocker.cli.get_log_dir", return_value=log_dir):
                result = runner.invoke(
                    main,
                    ["allow", "example.com", "--config-dir", str(config_dir)],
                )

        assert result.exit_code == 0
        assert "allowlist" in result.output.lower()

        # Step 2: Disallow domain
        add_disallow_mock(responses, "example.com")

        with patch("nextdns_blocker.common.get_log_dir", return_value=log_dir):
            with patch("nextdns_blocker.cli.get_log_dir", return_value=log_dir):
                result = runner.invoke(
                    main,
                    ["disallow", "example.com", "--config-dir", str(config_dir)],
                )

        assert result.exit_code == 0
        assert "removed" in result.output.lower() or "allowlist" in result.output.lower()


class TestAllowlistSyncIntegration:
    """Tests for allowlist integration with sync command."""

    @responses.activate
    def test_sync_adds_allowlist_domains(
        self,
        runner: CliRunner,
        tmp_path: Path,
    ) -> None:
        """Test that sync command adds domains from allowlist in config.json."""
        config_dir = tmp_path / "config"
        log_dir = tmp_path / "logs"
        config_dir.mkdir(parents=True)
        log_dir.mkdir(parents=True)

        (config_dir / ".env").write_text(
            f"NEXTDNS_API_KEY={TEST_API_KEY}\nNEXTDNS_PROFILE_ID={TEST_PROFILE_ID}\nTIMEZONE=UTC\n"
        )

        # config.json with allowlist (must have at least one domain in domains)
        domains_data = {
            "blocklist": [
                {"domain": "youtube.com", "schedule": None},
            ],
            "allowlist": [
                {"domain": "trusted-site.com"},
            ],
        }
        (config_dir / "config.json").write_text(json.dumps(domains_data))

        # Domain not yet in allowlist
        add_denylist_mock(responses, domains=[])
        add_allowlist_mock(responses, domains=[])
        add_allow_mock(responses, "trusted-site.com")

        with patch("nextdns_blocker.common.get_log_dir", return_value=log_dir):
            with patch("nextdns_blocker.cli.get_log_dir", return_value=log_dir):
                result = runner.invoke(
                    main,
                    ["sync", "--config-dir", str(config_dir), "-v"],
                )

        assert result.exit_code == 0
