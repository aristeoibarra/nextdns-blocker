"""Enable execution with python -m nextdns_blocker."""

from .category_cli import register_category
from .cli import main
from .config_cli import register_config
from .fix_cli import register_fix
from .list_cli import register_allowlist, register_denylist
from .nextdns_cli import register_nextdns
from .pending_cli import register_pending
from .protection_cli import register_protection
from .status_cli import register_status
from .watchdog import register_watchdog

# Register subcommands
register_watchdog(main)
register_config(main)
register_pending(main)
register_category(main)
register_denylist(main)
register_allowlist(main)
register_nextdns(main)
register_protection(main)
register_status(main)
register_fix(main)

if __name__ == "__main__":
    main()
