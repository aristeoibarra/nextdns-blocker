"""Enable execution with python -m nextdns_blocker."""

from .cli import main
from .watchdog import register_watchdog

# Register watchdog subcommand
register_watchdog(main)

if __name__ == "__main__":
    main()
