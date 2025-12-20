"""Custom exceptions for NextDNS Blocker.

This module defines the exception hierarchy for the NextDNS Blocker application.
All exceptions inherit from NextDNSBlockerError to allow catching all
application-specific errors with a single except clause.

Example:
    try:
        config = load_config()
        client = NextDNSClient(config["api_key"], config["profile_id"])
        client.block("example.com")
    except ConfigurationError as e:
        print(f"Configuration problem: {e}")
    except APIError as e:
        print(f"API request failed: {e}")
    except NextDNSBlockerError as e:
        print(f"General error: {e}")
"""


class NextDNSBlockerError(Exception):
    """Base exception for all NextDNS Blocker errors.

    This is the root of the exception hierarchy. Catching this exception
    will catch all application-specific errors.

    Attributes:
        message: Human-readable error description
    """

    pass


class ConfigurationError(NextDNSBlockerError):
    """Raised when configuration is invalid or missing.

    This exception is raised when:
    - Required configuration files (.env, config.json) are missing
    - API credentials are missing or have invalid format
    - Timezone setting is invalid
    - Domain configuration has validation errors

    Example:
        if not api_key:
            raise ConfigurationError("Missing NEXTDNS_API_KEY in .env")
    """

    pass


class DomainValidationError(NextDNSBlockerError):
    """Raised when domain validation fails.

    This exception is raised when:
    - Domain format is invalid (e.g., contains invalid characters)
    - Domain is empty or None
    - Domain exceeds maximum length

    Example:
        if not validate_domain(domain):
            raise DomainValidationError(f"Invalid domain: {domain}")
    """

    pass


class APIError(NextDNSBlockerError):
    """Raised when NextDNS API request fails.

    This exception is raised when:
    - API request times out after all retries
    - API returns an error status code
    - Network connectivity issues prevent request completion

    Example:
        result = self.request("GET", endpoint)
        if result is None:
            raise APIError(f"API request failed: {endpoint}")
    """

    pass
