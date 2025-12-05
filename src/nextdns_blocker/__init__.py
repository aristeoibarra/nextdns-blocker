"""NextDNS Blocker - Automated domain blocking with per-domain scheduling."""

__version__ = "5.0.0"

from .client import NextDNSClient
from .config import (
    get_config_dir,
    get_data_dir,
    get_log_dir,
    get_protected_domains,
    load_config,
    load_domains,
)
from .exceptions import (
    APIError,
    ConfigurationError,
    DomainValidationError,
    NextDNSBlockerError,
)
from .scheduler import ScheduleEvaluator

__all__ = [
    "__version__",
    "NextDNSClient",
    "ScheduleEvaluator",
    "load_config",
    "load_domains",
    "get_config_dir",
    "get_data_dir",
    "get_log_dir",
    "get_protected_domains",
    "NextDNSBlockerError",
    "ConfigurationError",
    "DomainValidationError",
    "APIError",
]
