"""Pytest fixtures for nextdns-blocker tests."""

import pytest
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


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
                    "time_ranges": [
                        {"start": "09:00", "end": "17:00"}
                    ]
                },
                {
                    "days": ["saturday", "sunday"],
                    "time_ranges": [
                        {"start": "10:00", "end": "22:00"}
                    ]
                }
            ]
        }
    }


@pytest.fixture
def always_blocked_config():
    """Domain config that should always be blocked (no schedule)."""
    return {
        "domain": "blocked.com",
        "description": "Always blocked",
        "schedule": None
    }


@pytest.fixture
def overnight_schedule_config():
    """Domain config with overnight time range (crosses midnight)."""
    return {
        "domain": "overnight.com",
        "schedule": {
            "available_hours": [
                {
                    "days": ["friday", "saturday"],
                    "time_ranges": [
                        {"start": "22:00", "end": "02:00"}
                    ]
                }
            ]
        }
    }
