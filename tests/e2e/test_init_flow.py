"""E2E tests for the initialization (onboarding) flow.

Tests the complete setup wizard including:
- Creating configuration files
- Validating API credentials
- Creating sample config.json
- Verifying sync works after init
"""

from __future__ import annotations

import json
import os
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


class TestInitNonInteractive:
    """Tests for non-interactive initialization."""

    @responses.activate
    def test_init_creates_env_file(
        self,
        runner: CliRunner,
        tmp_path: Path,
        clean_env: None,
    ) -> None:
        """Test that init --non-interactive creates .env file with correct content."""
        config_dir = tmp_path / "config"

        # Mock API validation call
        responses.add(
            responses.GET,
            f"{API_URL}/profiles/{TEST_PROFILE_ID}/denylist",
            json={"data": []},
            status=200,
        )

        # Set environment variables for non-interactive mode
        env = {
            "NEXTDNS_API_KEY": TEST_API_KEY,
            "NEXTDNS_PROFILE_ID": TEST_PROFILE_ID,
            "TIMEZONE": TEST_TIMEZONE,
        }

        # Mock scheduler installation and initial sync to avoid side effects
        with patch("nextdns_blocker.init.install_scheduling", return_value=(True, "mock")):
            with patch("nextdns_blocker.init.run_initial_sync", return_value=True):
                with patch.dict(os.environ, env, clear=False):
                    result = runner.invoke(
                        main,
                        ["init", "--non-interactive", "--config-dir", str(config_dir)],
                    )

        assert result.exit_code == 0, f"Init failed: {result.output}"

        # Verify .env file was created
        env_file = config_dir / ".env"
        assert env_file.exists(), "Expected .env file to be created"

        env_content = env_file.read_text()
        assert TEST_API_KEY in env_content
        assert TEST_PROFILE_ID in env_content

        # Verify config.json was created with timezone
        config_file = config_dir / "config.json"
        assert config_file.exists(), "Expected config.json to be created"

    @responses.activate
    def test_init_non_interactive_creates_config_json(
        self,
        runner: CliRunner,
        tmp_path: Path,
        clean_env: None,
    ) -> None:
        """Test that init --non-interactive creates .env and config.json."""
        config_dir = tmp_path / "config"

        # Mock API validation
        responses.add(
            responses.GET,
            f"{API_URL}/profiles/{TEST_PROFILE_ID}/denylist",
            json={"data": []},
            status=200,
        )

        # Mock scheduler installation
        with patch("nextdns_blocker.init.install_scheduling", return_value=(True, "mock")):
            with patch("nextdns_blocker.init.run_initial_sync", return_value=True):
                env = {
                    "NEXTDNS_API_KEY": TEST_API_KEY,
                    "NEXTDNS_PROFILE_ID": TEST_PROFILE_ID,
                }

                with patch.dict(os.environ, env, clear=False):
                    result = runner.invoke(
                        main,
                        ["init", "--non-interactive", "--config-dir", str(config_dir)],
                    )

        assert result.exit_code == 0, f"Init failed: {result.output}"

        # Both .env and config.json should be created
        env_file = config_dir / ".env"
        assert env_file.exists(), "Expected .env to be created"

        config_file = config_dir / "config.json"
        assert config_file.exists(), "Expected config.json to be created"

    @responses.activate
    def test_init_with_invalid_credentials_fails(
        self,
        runner: CliRunner,
        tmp_path: Path,
        clean_env: None,
    ) -> None:
        """Test that init fails gracefully with invalid API credentials."""
        config_dir = tmp_path / "config"

        # Mock API returning 401 Unauthorized
        responses.add(
            responses.GET,
            f"{API_URL}/profiles/{TEST_PROFILE_ID}/denylist",
            json={"error": "Unauthorized"},
            status=401,
        )

        env = {
            "NEXTDNS_API_KEY": "invalid-key",
            "NEXTDNS_PROFILE_ID": TEST_PROFILE_ID,
            "TIMEZONE": TEST_TIMEZONE,
        }

        with patch.dict(os.environ, env, clear=False):
            result = runner.invoke(
                main,
                ["init", "--non-interactive", "--config-dir", str(config_dir)],
            )

        assert result.exit_code != 0, "Init should fail with invalid credentials"

    @responses.activate
    def test_init_with_invalid_timezone_fails(
        self,
        runner: CliRunner,
        tmp_path: Path,
        clean_env: None,
    ) -> None:
        """Test that init fails with invalid timezone."""
        config_dir = tmp_path / "config"

        env = {
            "NEXTDNS_API_KEY": TEST_API_KEY,
            "NEXTDNS_PROFILE_ID": TEST_PROFILE_ID,
            "TIMEZONE": "Invalid/Timezone",
        }

        with patch.dict(os.environ, env, clear=False):
            result = runner.invoke(
                main,
                ["init", "--non-interactive", "--config-dir", str(config_dir)],
            )

        assert result.exit_code != 0, "Init should fail with invalid timezone"


class TestInitThenSync:
    """Tests for the complete init → sync workflow."""

    @responses.activate
    def test_sync_works_after_init_with_domains_file(
        self,
        runner: CliRunner,
        tmp_path: Path,
        clean_env: None,
    ) -> None:
        """Test that sync command works after init when config.json exists."""
        config_dir = tmp_path / "config"
        config_dir.mkdir(parents=True)
        log_dir = tmp_path / "logs"
        log_dir.mkdir(parents=True)

        # Mock API validation for init
        responses.add(
            responses.GET,
            f"{API_URL}/profiles/{TEST_PROFILE_ID}/denylist",
            json={"data": []},
            status=200,
        )

        env = {
            "NEXTDNS_API_KEY": TEST_API_KEY,
            "NEXTDNS_PROFILE_ID": TEST_PROFILE_ID,
            "TIMEZONE": TEST_TIMEZONE,
        }

        # Step 1: Run init (mocking scheduler and initial sync)
        with patch("nextdns_blocker.init.install_scheduling", return_value=(True, "mock")):
            with patch("nextdns_blocker.init.run_initial_sync", return_value=True):
                with patch.dict(os.environ, env, clear=False):
                    result = runner.invoke(
                        main,
                        ["init", "--non-interactive", "--config-dir", str(config_dir)],
                    )

        assert result.exit_code == 0, f"Init failed: {result.output}"

        # Step 2: Update config.json with domain (created by init with empty blocklist)
        config_data = {
            "version": "1.0",
            "settings": {"timezone": TEST_TIMEZONE, "editor": None},
            "blocklist": [
                {
                    "domain": "test.com",
                    "schedule": {
                        "available_hours": [
                            {
                                "days": ["monday"],
                                "time_ranges": [{"start": "09:00", "end": "17:00"}],
                            }
                        ]
                    },
                }
            ],
            "allowlist": [],
        }
        (config_dir / "config.json").write_text(json.dumps(config_data))

        # Step 3: Add mocks for sync command
        responses.add(
            responses.GET,
            f"{API_URL}/profiles/{TEST_PROFILE_ID}/denylist",
            json={"data": []},
            status=200,
        )
        responses.add(
            responses.GET,
            f"{API_URL}/profiles/{TEST_PROFILE_ID}/allowlist",
            json={"data": []},
            status=200,
        )
        responses.add(
            responses.POST,
            f"{API_URL}/profiles/{TEST_PROFILE_ID}/denylist",
            json={"success": True},
            status=200,
        )

        # Step 4: Run sync
        with patch("nextdns_blocker.common.get_log_dir", return_value=log_dir):
            with patch("nextdns_blocker.cli.get_log_dir", return_value=log_dir):
                result = runner.invoke(
                    main,
                    ["sync", "--config-dir", str(config_dir)],
                )

        assert result.exit_code == 0, f"Sync failed: {result.output}"


class TestInitIdempotent:
    """Tests for re-running init on existing configuration."""

    @responses.activate
    def test_init_preserves_existing_config_json(
        self,
        runner: CliRunner,
        tmp_path: Path,
        clean_env: None,
    ) -> None:
        """Test that running init again doesn't overwrite existing config.json."""
        config_dir = tmp_path / "config"
        config_dir.mkdir(parents=True)

        # Create existing config.json with custom content
        custom_config = {"blocklist": [{"domain": "custom-domain.com", "schedule": None}]}
        config_file = config_dir / "config.json"
        config_file.write_text(json.dumps(custom_config))

        # Mock API
        responses.add(
            responses.GET,
            f"{API_URL}/profiles/{TEST_PROFILE_ID}/denylist",
            json={"data": []},
            status=200,
        )

        env = {
            "NEXTDNS_API_KEY": TEST_API_KEY,
            "NEXTDNS_PROFILE_ID": TEST_PROFILE_ID,
            "TIMEZONE": TEST_TIMEZONE,
        }

        with patch("nextdns_blocker.init.install_scheduling", return_value=(True, "mock")):
            with patch("nextdns_blocker.init.run_initial_sync", return_value=True):
                with patch.dict(os.environ, env, clear=False):
                    result = runner.invoke(
                        main,
                        ["init", "--non-interactive", "--config-dir", str(config_dir)],
                    )

        assert result.exit_code == 0

        # Verify config.json still has custom content
        final_config = json.loads(config_file.read_text())
        assert final_config["blocklist"][0]["domain"] == "custom-domain.com"
