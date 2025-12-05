"""NextDNS Blocker - Automated domain blocking with per-domain scheduling."""

__version__ = "5.0.0"

from .client import NextDNSClient
from .config import load_config, load_domains, get_protected_domains
from .exceptions import (
    NextDNSBlockerError,
    ConfigurationError,
    DomainValidationError,
    APIError,
)
from .scheduler import ScheduleEvaluator

__all__ = [
    "__version__",
    "NextDNSClient",
    "ScheduleEvaluator",
    "load_config",
    "load_domains",
    "get_protected_domains",
    "NextDNSBlockerError",
    "ConfigurationError",
    "DomainValidationError",
    "APIError",
]
