"""NextDNS Blocker - Automated domain blocking with per-domain scheduling."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("nextdns-blocker")
except PackageNotFoundError:
    __version__ = "0.0.0"  # Development without install

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
from .notifications import send_discord_notification
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
    "send_discord_notification",
]
