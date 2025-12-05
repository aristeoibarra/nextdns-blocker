"""Custom exceptions for NextDNS Blocker."""


class NextDNSBlockerError(Exception):
    """Base exception for NextDNS Blocker."""

    pass


class ConfigurationError(NextDNSBlockerError):
    """Raised when configuration is invalid or missing."""

    pass


class DomainValidationError(NextDNSBlockerError):
    """Raised when domain validation fails."""

    pass


class APIError(NextDNSBlockerError):
    """Raised when API request fails."""

    pass
