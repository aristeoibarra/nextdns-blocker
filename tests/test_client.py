"""Tests for NextDNSClient class."""

import pytest
import responses
import requests

from nextdns_blocker import NextDNSClient, API_URL


@pytest.fixture
def client():
    """Create a NextDNSClient instance for testing."""
    return NextDNSClient("test_api_key", "test_profile")


@pytest.fixture
def mock_denylist():
    """Sample denylist response."""
    return {
        "data": [
            {"id": "example.com", "active": True},
            {"id": "blocked.com", "active": True}
        ]
    }


class TestGetDenylist:
    """Tests for get_denylist method."""

    @responses.activate
    def test_get_denylist_success(self, client, mock_denylist):
        responses.add(
            responses.GET,
            f"{API_URL}/profiles/test_profile/denylist",
            json=mock_denylist,
            status=200
        )
        result = client.get_denylist()
        assert result == mock_denylist["data"]

    @responses.activate
    def test_get_denylist_empty(self, client):
        responses.add(
            responses.GET,
            f"{API_URL}/profiles/test_profile/denylist",
            json={"data": []},
            status=200
        )
        result = client.get_denylist()
        assert result == []

    @responses.activate
    def test_get_denylist_timeout(self, client):
        responses.add(
            responses.GET,
            f"{API_URL}/profiles/test_profile/denylist",
            body=requests.exceptions.Timeout()
        )
        result = client.get_denylist()
        assert result is None

    @responses.activate
    def test_get_denylist_server_error(self, client):
        responses.add(
            responses.GET,
            f"{API_URL}/profiles/test_profile/denylist",
            status=500
        )
        result = client.get_denylist()
        assert result is None


class TestFindDomain:
    """Tests for find_domain method."""

    @responses.activate
    def test_find_domain_exists(self, client, mock_denylist):
        responses.add(
            responses.GET,
            f"{API_URL}/profiles/test_profile/denylist",
            json=mock_denylist,
            status=200
        )
        result = client.find_domain("example.com")
        assert result == "example.com"

    @responses.activate
    def test_find_domain_not_found(self, client, mock_denylist):
        responses.add(
            responses.GET,
            f"{API_URL}/profiles/test_profile/denylist",
            json=mock_denylist,
            status=200
        )
        result = client.find_domain("notfound.com")
        assert result is None

    @responses.activate
    def test_find_domain_api_error(self, client):
        responses.add(
            responses.GET,
            f"{API_URL}/profiles/test_profile/denylist",
            status=500
        )
        result = client.find_domain("example.com")
        assert result is None


class TestBlock:
    """Tests for block method."""

    @responses.activate
    def test_block_new_domain(self, client):
        # First call: get denylist (domain not found)
        responses.add(
            responses.GET,
            f"{API_URL}/profiles/test_profile/denylist",
            json={"data": []},
            status=200
        )
        # Second call: add to denylist
        responses.add(
            responses.POST,
            f"{API_URL}/profiles/test_profile/denylist",
            json={"success": True},
            status=200
        )
        result = client.block("newdomain.com")
        assert result is True

    @responses.activate
    def test_block_already_blocked(self, client, mock_denylist):
        responses.add(
            responses.GET,
            f"{API_URL}/profiles/test_profile/denylist",
            json=mock_denylist,
            status=200
        )
        # Domain already exists, no POST should be made
        result = client.block("example.com")
        assert result is True
        assert len(responses.calls) == 1  # Only GET, no POST

    @responses.activate
    def test_block_api_error(self, client):
        responses.add(
            responses.GET,
            f"{API_URL}/profiles/test_profile/denylist",
            json={"data": []},
            status=200
        )
        responses.add(
            responses.POST,
            f"{API_URL}/profiles/test_profile/denylist",
            status=500
        )
        result = client.block("newdomain.com")
        assert result is False


class TestUnblock:
    """Tests for unblock method."""

    @responses.activate
    def test_unblock_existing_domain(self, client, mock_denylist):
        responses.add(
            responses.GET,
            f"{API_URL}/profiles/test_profile/denylist",
            json=mock_denylist,
            status=200
        )
        responses.add(
            responses.DELETE,
            f"{API_URL}/profiles/test_profile/denylist/example.com",
            json={"success": True},
            status=200
        )
        result = client.unblock("example.com")
        assert result is True

    @responses.activate
    def test_unblock_not_found(self, client):
        responses.add(
            responses.GET,
            f"{API_URL}/profiles/test_profile/denylist",
            json={"data": []},
            status=200
        )
        # Domain not in denylist, should return True (already unblocked)
        result = client.unblock("notfound.com")
        assert result is True
        assert len(responses.calls) == 1  # Only GET, no DELETE

    @responses.activate
    def test_unblock_api_error(self, client, mock_denylist):
        responses.add(
            responses.GET,
            f"{API_URL}/profiles/test_profile/denylist",
            json=mock_denylist,
            status=200
        )
        responses.add(
            responses.DELETE,
            f"{API_URL}/profiles/test_profile/denylist/example.com",
            status=500
        )
        result = client.unblock("example.com")
        assert result is False


class TestRequestRetry:
    """Tests for retry logic in request method."""

    @responses.activate
    def test_retry_on_timeout(self, client):
        # First two calls timeout, third succeeds
        responses.add(
            responses.GET,
            f"{API_URL}/profiles/test_profile/denylist",
            body=requests.exceptions.Timeout()
        )
        responses.add(
            responses.GET,
            f"{API_URL}/profiles/test_profile/denylist",
            body=requests.exceptions.Timeout()
        )
        responses.add(
            responses.GET,
            f"{API_URL}/profiles/test_profile/denylist",
            json={"data": []},
            status=200
        )
        result = client.get_denylist()
        assert result == []
        assert len(responses.calls) == 3

    @responses.activate
    def test_max_retries_exceeded(self, client):
        # All calls timeout
        for _ in range(3):
            responses.add(
                responses.GET,
                f"{API_URL}/profiles/test_profile/denylist",
                body=requests.exceptions.Timeout()
            )
        result = client.get_denylist()
        assert result is None
        assert len(responses.calls) == 3


class TestHeaders:
    """Tests for API headers."""

    @responses.activate
    def test_api_key_header(self, client):
        responses.add(
            responses.GET,
            f"{API_URL}/profiles/test_profile/denylist",
            json={"data": []},
            status=200
        )
        client.get_denylist()
        assert responses.calls[0].request.headers["X-Api-Key"] == "test_api_key"

    @responses.activate
    def test_content_type_header(self, client):
        responses.add(
            responses.GET,
            f"{API_URL}/profiles/test_profile/denylist",
            json={"data": []},
            status=200
        )
        client.get_denylist()
        assert responses.calls[0].request.headers["Content-Type"] == "application/json"
