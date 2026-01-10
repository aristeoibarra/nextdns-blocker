"""Enable execution with python -m nextdns_blocker."""

from .category_cli import register_category
from .cli import main
from .config_cli import register_config
from .list_cli import register_allowlist, register_denylist
from .panic_cli import register_panic
from .pending_cli import register_pending
from .watchdog import register_watchdog

# Register subcommands
register_watchdog(main)
register_config(main)
register_pending(main)
register_panic(main)
register_category(main)
register_denylist(main)
register_allowlist(main)

if __name__ == "__main__":
    main()
