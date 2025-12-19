"""Pytest fixtures for nextdns-blocker tests."""

import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

# Add src directory to path for imports
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_project_root, "src"))


@pytest.fixture
def sample_domain_config():
    """Sample domain configuration for testing."""
    return {
        "domain": "example.com",
        "description": "Test domain",
        "schedule": {
            "available_hours": [
                {
                    "days": ["monday", "tuesday", "wednesday", "thursday", "friday"],
                    "time_ranges": [{"start": "09:00", "end": "17:00"}],
                },
                {
                    "days": ["saturday", "sunday"],
                    "time_ranges": [{"start": "10:00", "end": "22:00"}],
                },
            ]
        },
    }


@pytest.fixture
def always_blocked_config():
    """Domain config that should always be blocked (no schedule)."""
    return {"domain": "blocked.com", "description": "Always blocked", "schedule": None}


@pytest.fixture
def overnight_schedule_config():
    """Domain config with overnight time range (crosses midnight)."""
    return {
        "domain": "overnight.com",
        "schedule": {
            "available_hours": [
                {
                    "days": ["friday", "saturday"],
                    "time_ranges": [{"start": "22:00", "end": "02:00"}],
                }
            ]
        },
    }


@pytest.fixture
def protected_domain_config():
    """Domain config marked as protected."""
    return {
        "domain": "protected.example.com",
        "description": "Protected domain",
        "protected": True,
        "schedule": None,
    }


@pytest.fixture
def mixed_domains_config():
    """List of domains with mixed protected status."""
    return [
        {
            "domain": "normal.com",
            "schedule": {
                "available_hours": [
                    {"days": ["monday"], "time_ranges": [{"start": "09:00", "end": "17:00"}]}
                ]
            },
        },
        {"domain": "protected1.com", "protected": True, "schedule": None},
        {"domain": "another.com", "protected": False, "schedule": None},
        {"domain": "protected2.com", "protected": True, "schedule": None},
    ]


@pytest.fixture
def temp_dir():
    """Create a temporary directory for test files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def mock_env_vars():
    """Mock environment variables for configuration."""
    env_vars = {
        "NEXTDNS_API_KEY": "test_api_key_12345",  # Must be at least 8 chars
        "NEXTDNS_PROFILE_ID": "testprofile",  # Must be 4-30 chars
        "TIMEZONE": "UTC",
    }
    with patch.dict(os.environ, env_vars, clear=False):
        yield env_vars


@pytest.fixture
def domains_json_content():
    """Sample config.json content."""
    return {
        "blocklist": [
            {
                "domain": "example.com",
                "description": "Test domain",
                "protected": False,
                "schedule": {
                    "available_hours": [
                        {
                            "days": ["monday", "tuesday"],
                            "time_ranges": [{"start": "09:00", "end": "17:00"}],
                        }
                    ]
                },
            },
            {"domain": "blocked.com", "protected": True, "schedule": None},
        ]
    }


@pytest.fixture
def invalid_domains_json():
    """Invalid config.json content for error testing."""
    return {
        "blocklist": [
            {"domain": ""},  # Empty domain
            {"description": "Missing domain"},  # No domain field
            {"domain": "bad-schedule.com", "schedule": "not a dict"},  # Invalid schedule type
        ]
    }


@pytest.fixture(autouse=True)
def reset_notification_rate_limit():
    """Reset Discord notification rate limit before each test."""
    try:
        from nextdns_blocker.notifications import _reset_rate_limit

        _reset_rate_limit()
    except ImportError:
        pass  # Module not yet loaded
    yield
    # Reset again after test to clean up
    try:
        from nextdns_blocker.notifications import _reset_rate_limit

        _reset_rate_limit()
    except ImportError:
        pass
