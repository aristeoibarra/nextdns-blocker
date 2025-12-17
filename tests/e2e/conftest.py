"""E2E-specific fixtures for nextdns-blocker tests.

These fixtures create real files and mock HTTP calls (not internal functions),
allowing end-to-end testing of complete user workflows.
"""

from __future__ import annotations

import json
import os
from collections.abc import Generator
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
import responses
from click.testing import CliRunner

from nextdns_blocker.client import API_URL

# =============================================================================
# CONSTANTS
# =============================================================================

TEST_API_KEY = "test-api-key-12345678"
TEST_PROFILE_ID = "abc123"
TEST_TIMEZONE = "America/Mexico_City"


# =============================================================================
# FIXTURES: CLI RUNNER
# =============================================================================


@pytest.fixture
def runner() -> CliRunner:
    """Create a Click CLI runner for testing commands."""
    return CliRunner()


@pytest.fixture
def isolated_runner() -> Generator[CliRunner, None, None]:
    """Create an isolated CLI runner with a temporary directory."""
    runner = CliRunner()
    with runner.isolated_filesystem():
        yield runner


# =============================================================================
# FIXTURES: CONFIG DIRECTORY
# =============================================================================


@pytest.fixture
def e2e_config_dir(tmp_path: Path) -> Path:
    """Create a temporary config directory for e2e tests."""
    config_dir = tmp_path / "config"
    config_dir.mkdir(parents=True)
    return config_dir


@pytest.fixture
def e2e_log_dir(tmp_path: Path) -> Path:
    """Create a temporary log directory for e2e tests."""
    log_dir = tmp_path / "logs"
    log_dir.mkdir(parents=True)
    return log_dir


@pytest.fixture
def setup_env_file(e2e_config_dir: Path) -> Path:
    """Create a .env file with test credentials."""
    env_file = e2e_config_dir / ".env"
    env_file.write_text(
        f"NEXTDNS_API_KEY={TEST_API_KEY}\n"
        f"NEXTDNS_PROFILE_ID={TEST_PROFILE_ID}\n"
        f"TIMEZONE={TEST_TIMEZONE}\n"
    )
    return env_file


@pytest.fixture
def setup_domains_file(e2e_config_dir: Path) -> Path:
    """Create a basic config.json file."""
    domains_file = e2e_config_dir / "config.json"
    domains_data = {
        "blocklist": [
            {
                "domain": "youtube.com",
                "description": "Video streaming",
                "protected": False,
                "schedule": {
                    "available_hours": [
                        {
                            "days": ["monday", "tuesday", "wednesday", "thursday", "friday"],
                            "time_ranges": [{"start": "09:00", "end": "17:00"}],
                        }
                    ]
                },
            },
            {
                "domain": "twitter.com",
                "description": "Social media",
                "protected": False,
                "schedule": {
                    "available_hours": [
                        {
                            "days": ["saturday", "sunday"],
                            "time_ranges": [{"start": "10:00", "end": "22:00"}],
                        }
                    ]
                },
            },
            {
                "domain": "gambling.com",
                "description": "Always blocked gambling site",
                "protected": True,
                "schedule": None,
            },
        ]
    }
    domains_file.write_text(json.dumps(domains_data, indent=2))
    return domains_file


@pytest.fixture
def e2e_config(
    e2e_config_dir: Path,
    e2e_log_dir: Path,
    setup_env_file: Path,
    setup_domains_file: Path,
) -> dict[str, Any]:
    """Set up a complete e2e test environment with config and log directories."""
    return {
        "config_dir": e2e_config_dir,
        "log_dir": e2e_log_dir,
        "env_file": setup_env_file,
        "domains_file": setup_domains_file,
        "api_key": TEST_API_KEY,
        "profile_id": TEST_PROFILE_ID,
        "timezone": TEST_TIMEZONE,
    }


# =============================================================================
# FIXTURES: MOCK LOG DIRECTORY
# =============================================================================


@pytest.fixture
def mock_log_dir(e2e_log_dir: Path) -> Generator[Path, None, None]:
    """Mock the log directory to use our temp directory."""
    with patch("nextdns_blocker.common.get_log_dir", return_value=e2e_log_dir):
        with patch("nextdns_blocker.cli.get_log_dir", return_value=e2e_log_dir):
            yield e2e_log_dir


# =============================================================================
# FIXTURES: NEXTDNS API MOCKS
# =============================================================================


@pytest.fixture
def mock_nextdns_api() -> Generator[responses.RequestsMock, None, None]:
    """
    Activate responses mock for NextDNS API calls.

    This provides HTTP-level mocking rather than function-level mocking,
    allowing us to test the full HTTP client behavior.
    """
    with responses.RequestsMock() as rsps:
        yield rsps


@pytest.fixture
def mock_empty_denylist(mock_nextdns_api: responses.RequestsMock) -> responses.RequestsMock:
    """Set up mock for an empty denylist."""
    mock_nextdns_api.add(
        responses.GET,
        f"{API_URL}/profiles/{TEST_PROFILE_ID}/denylist",
        json={"data": []},
        status=200,
    )
    return mock_nextdns_api


@pytest.fixture
def mock_empty_allowlist(mock_nextdns_api: responses.RequestsMock) -> responses.RequestsMock:
    """Set up mock for an empty allowlist."""
    mock_nextdns_api.add(
        responses.GET,
        f"{API_URL}/profiles/{TEST_PROFILE_ID}/allowlist",
        json={"data": []},
        status=200,
    )
    return mock_nextdns_api


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================


def add_denylist_mock(
    rsps: responses.RequestsMock,
    domains: list[str] | None = None,
    profile_id: str = TEST_PROFILE_ID,
) -> None:
    """Add a GET denylist mock with specified domains."""
    data = [{"id": d, "active": True} for d in (domains or [])]
    rsps.add(
        responses.GET,
        f"{API_URL}/profiles/{profile_id}/denylist",
        json={"data": data},
        status=200,
    )


def add_allowlist_mock(
    rsps: responses.RequestsMock,
    domains: list[str] | None = None,
    profile_id: str = TEST_PROFILE_ID,
) -> None:
    """Add a GET allowlist mock with specified domains."""
    data = [{"id": d, "active": True} for d in (domains or [])]
    rsps.add(
        responses.GET,
        f"{API_URL}/profiles/{profile_id}/allowlist",
        json={"data": data},
        status=200,
    )


def add_block_mock(
    rsps: responses.RequestsMock,
    domain: str,
    profile_id: str = TEST_PROFILE_ID,
    success: bool = True,
) -> None:
    """Add a POST denylist mock for blocking a domain."""
    rsps.add(
        responses.POST,
        f"{API_URL}/profiles/{profile_id}/denylist",
        json={"id": domain, "active": True} if success else {"error": "Failed"},
        status=200 if success else 500,
    )


def add_unblock_mock(
    rsps: responses.RequestsMock,
    domain: str,
    profile_id: str = TEST_PROFILE_ID,
    success: bool = True,
) -> None:
    """Add a DELETE denylist mock for unblocking a domain."""
    rsps.add(
        responses.DELETE,
        f"{API_URL}/profiles/{profile_id}/denylist/{domain}",
        json={"success": True} if success else {"error": "Failed"},
        status=200 if success else 500,
    )


def add_allow_mock(
    rsps: responses.RequestsMock,
    domain: str,
    profile_id: str = TEST_PROFILE_ID,
    success: bool = True,
) -> None:
    """Add a POST allowlist mock for allowing a domain."""
    rsps.add(
        responses.POST,
        f"{API_URL}/profiles/{profile_id}/allowlist",
        json={"id": domain, "active": True} if success else {"error": "Failed"},
        status=200 if success else 500,
    )


def add_disallow_mock(
    rsps: responses.RequestsMock,
    domain: str,
    profile_id: str = TEST_PROFILE_ID,
    success: bool = True,
) -> None:
    """Add a DELETE allowlist mock for disallowing a domain."""
    rsps.add(
        responses.DELETE,
        f"{API_URL}/profiles/{profile_id}/allowlist/{domain}",
        json={"success": True} if success else {"error": "Failed"},
        status=200 if success else 500,
    )


# =============================================================================
# FIXTURES: COMPLETE API SETUP
# =============================================================================


@pytest.fixture
def mock_api_for_sync(mock_nextdns_api: responses.RequestsMock) -> responses.RequestsMock:
    """Set up complete API mocks for a sync operation."""
    # Initial state: empty denylist and allowlist
    add_denylist_mock(mock_nextdns_api, domains=[])
    add_allowlist_mock(mock_nextdns_api, domains=[])

    # Add generic POST/DELETE handlers for any domain
    mock_nextdns_api.add(
        responses.POST,
        f"{API_URL}/profiles/{TEST_PROFILE_ID}/denylist",
        json={"success": True},
        status=200,
    )
    mock_nextdns_api.add(
        responses.DELETE,
        f"{API_URL}/profiles/{TEST_PROFILE_ID}/denylist/youtube.com",
        json={"success": True},
        status=200,
    )
    mock_nextdns_api.add(
        responses.DELETE,
        f"{API_URL}/profiles/{TEST_PROFILE_ID}/denylist/twitter.com",
        json={"success": True},
        status=200,
    )
    mock_nextdns_api.add(
        responses.DELETE,
        f"{API_URL}/profiles/{TEST_PROFILE_ID}/denylist/gambling.com",
        json={"success": True},
        status=200,
    )

    return mock_nextdns_api


# =============================================================================
# FIXTURES: ENVIRONMENT ISOLATION
# =============================================================================


@pytest.fixture
def clean_env() -> Generator[None, None, None]:
    """Remove NextDNS environment variables for clean testing."""
    env_vars = ["NEXTDNS_API_KEY", "NEXTDNS_PROFILE_ID", "TIMEZONE", "DOMAINS_URL"]
    original = {k: os.environ.get(k) for k in env_vars}

    for var in env_vars:
        os.environ.pop(var, None)

    yield

    # Restore original values
    for var, value in original.items():
        if value is not None:
            os.environ[var] = value
        else:
            os.environ.pop(var, None)


@pytest.fixture(autouse=True, scope="module")
def isolate_test_environment(
    tmp_path_factory: pytest.TempPathFactory,
) -> Generator[None, None, None]:
    """Isolate each test module from system configuration and cache.

    Using scope="module" runs this fixture once per test file instead of
    once per test function, significantly improving test performance.
    """
    # Create a module-level temp directory for cache
    # Save and clear environment variables that might interfere
    env_vars = ["NEXTDNS_API_KEY", "NEXTDNS_PROFILE_ID", "TIMEZONE"]
    original = {k: os.environ.get(k) for k in env_vars}
    for var in env_vars:
        os.environ.pop(var, None)

    yield

    # Restore original environment
    for var, value in original.items():
        if value is not None:
            os.environ[var] = value
        else:
            os.environ.pop(var, None)
