#!/usr/bin/env python3
"""
NextDNS Config Blocker
Blocks/unblocks access to my.nextdns.io using NextDNS API
"""

import os
import sys
import logging
import json
from typing import Optional, Dict, Any, List
from datetime import datetime, time
import requests
import pytz

LOG_DIR = os.path.expanduser("~/nextdns-blocker/logs")
os.makedirs(LOG_DIR, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(LOG_DIR, 'nextdns_blocker.log')),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

API_BASE_URL = "https://api.nextdns.io"


class NextDNSBlocker:
    """Manages blocking/unblocking domains in NextDNS"""

    def __init__(self, api_key: str, profile_id: str):
        self.api_key = api_key
        self.profile_id = profile_id
        self.headers = {
            "X-Api-Key": api_key,
            "Content-Type": "application/json"
        }

    def _make_request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict] = None
    ) -> Optional[Dict[str, Any]]:
        """Makes API request to NextDNS"""
        url = f"{API_BASE_URL}{endpoint}"

        try:
            if method == "GET":
                response = requests.get(url, headers=self.headers, timeout=10)
            elif method == "POST":
                response = requests.post(url, headers=self.headers, json=data, timeout=10)
            elif method == "DELETE":
                response = requests.delete(url, headers=self.headers, timeout=10)
            elif method == "PATCH":
                response = requests.patch(url, headers=self.headers, json=data, timeout=10)
            else:
                logger.error(f"Unsupported HTTP method: {method}")
                return None

            response.raise_for_status()

            if response.text:
                return response.json()
            return {"success": True}

        except requests.exceptions.RequestException as e:
            logger.error(f"API request error: {e}")
            if hasattr(e, 'response') and e.response is not None:
                logger.error(f"Server response: {e.response.text}")
            return None

    def get_denylist(self) -> Optional[list]:
        """Gets current denylist"""
        logger.info("Fetching current denylist...")
        response = self._make_request("GET", f"/profiles/{self.profile_id}/denylist")

        if response and "data" in response:
            return response["data"]
        return None

    def find_domain_in_denylist(self, domain: str) -> Optional[str]:
        """Searches for domain in denylist"""
        denylist = self.get_denylist()

        if denylist is None:
            return None

        for entry in denylist:
            if entry.get("id") == domain:
                logger.info(f"Domain '{domain}' found in denylist")
                return entry.get("id")

        logger.info(f"Domain '{domain}' NOT found in denylist")
        return None

    def block_domain(self, domain: str) -> bool:
        """Adds domain to denylist"""
        if self.find_domain_in_denylist(domain):
            logger.info(f"Domain '{domain}' already in denylist")
            return True

        logger.info(f"Adding '{domain}' to denylist...")
        data = {"id": domain, "active": True}

        response = self._make_request(
            "POST",
            f"/profiles/{self.profile_id}/denylist",
            data
        )

        if response:
            logger.info(f"✅ Domain '{domain}' blocked successfully")
            return True
        else:
            logger.error(f"❌ Error blocking '{domain}'")
            return False

    def unblock_domain(self, domain: str) -> bool:
        """Removes domain from denylist"""
        domain_id = self.find_domain_in_denylist(domain)

        if not domain_id:
            logger.info(f"Domain '{domain}' not in denylist, nothing to do")
            return True

        logger.info(f"Removing '{domain}' from denylist...")

        response = self._make_request(
            "DELETE",
            f"/profiles/{self.profile_id}/denylist/{domain_id}"
        )

        if response is not None:
            logger.info(f"✅ Domain '{domain}' unblocked successfully")
            return True
        else:
            logger.error(f"❌ Error unblocking '{domain}'")
            return False


class ScheduleEvaluator:
    """Evaluates if a domain should be blocked based on its schedule configuration"""

    DAYS_MAP = {
        'monday': 0,
        'tuesday': 1,
        'wednesday': 2,
        'thursday': 3,
        'friday': 4,
        'saturday': 5,
        'sunday': 6
    }

    def __init__(self, timezone_str: str = 'America/Mexico_City'):
        """Initialize with timezone"""
        try:
            self.timezone = pytz.timezone(timezone_str)
        except pytz.exceptions.UnknownTimeZoneError:
            logger.warning(f"Unknown timezone: {timezone_str}, using UTC")
            self.timezone = pytz.UTC

    def _parse_time(self, time_str: str) -> time:
        """Parse time string in format HH:MM to time object"""
        try:
            hours, minutes = map(int, time_str.split(':'))
            return time(hours, minutes)
        except (ValueError, AttributeError) as e:
            logger.error(f"Invalid time format: {time_str}, expected HH:MM")
            raise ValueError(f"Invalid time format: {time_str}")

    def _is_time_in_range(self, current_time: time, start_time: time, end_time: time) -> bool:
        """Check if current_time is between start_time and end_time"""
        if start_time <= end_time:
            # Normal range (e.g., 09:00 to 17:00)
            return start_time <= current_time <= end_time
        else:
            # Range crossing midnight (e.g., 22:00 to 02:00)
            return current_time >= start_time or current_time <= end_time

    def should_be_blocked(self, schedule_config: Dict) -> bool:
        """
        Determines if a domain should be blocked based on its schedule

        Schedule format:
        {
            "available_hours": [  # Hours when domain is ALLOWED (not blocked)
                {
                    "days": ["monday", "tuesday", ...],
                    "time_ranges": [
                        {"start": "09:00", "end": "12:00"},
                        {"start": "14:00", "end": "18:00"}
                    ]
                }
            ]
        }

        Returns True if domain should be BLOCKED (outside available hours)
        """
        if not schedule_config or 'available_hours' not in schedule_config:
            # No schedule configured, domain is always blocked
            logger.debug("No schedule configured, domain should be blocked")
            return True

        # Get current time in configured timezone
        now = datetime.now(self.timezone)
        current_day = now.weekday()  # 0 = Monday, 6 = Sunday
        current_time = now.time()

        logger.debug(f"Evaluating schedule at {now} (day={current_day}, time={current_time})")

        # Check if current time falls within any available hours
        for schedule_block in schedule_config['available_hours']:
            # Check if today is in the configured days
            configured_days = [self.DAYS_MAP[day.lower()] for day in schedule_block.get('days', [])]

            if current_day not in configured_days:
                continue

            # Check if current time is within any time range for today
            for time_range in schedule_block.get('time_ranges', []):
                start = self._parse_time(time_range['start'])
                end = self._parse_time(time_range['end'])

                if self._is_time_in_range(current_time, start, end):
                    logger.debug(f"Within available hours: {time_range['start']}-{time_range['end']}")
                    return False  # Within available hours, should NOT be blocked

        # Not within any available hours, should be blocked
        logger.debug("Outside available hours, domain should be blocked")
        return True


def load_domain_configs(script_dir: str) -> List[Dict]:
    """
    Loads domain configurations with schedules from domains.json

    Returns list of dicts with format:
    [
        {
            "domain": "example.com",
            "schedule": {
                "available_hours": [...]
            }
        }
    ]
    """
    json_file = os.path.join(script_dir, 'domains.json')

    if not os.path.exists(json_file):
        logger.error(f"❌ Configuration file not found: {json_file}")
        logger.error("Please create domains.json file. See domains.json.example for reference.")
        sys.exit(1)

    try:
        with open(json_file, 'r') as f:
            config = json.load(f)

        domains_config = config.get('domains', [])
        if not domains_config:
            logger.error("❌ No domains found in domains.json")
            sys.exit(1)

        logger.info(f"Loaded {len(domains_config)} domain(s) with schedules from domains.json")
        return domains_config

    except json.JSONDecodeError as e:
        logger.error(f"❌ Error parsing domains.json: {e}")
        logger.error("Please check your JSON syntax. Use: python3 -m json.tool domains.json")
        sys.exit(1)


def load_config() -> Dict[str, str]:
    """Loads configuration from .env file"""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    env_file = os.path.join(script_dir, '.env')

    if os.path.exists(env_file):
        logger.info(f"Loading config from {env_file}")
        with open(env_file, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    key, value = line.split('=', 1)
                    os.environ[key.strip()] = value.strip()

    config = {
        'api_key': os.getenv('NEXTDNS_API_KEY'),
        'profile_id': os.getenv('NEXTDNS_PROFILE_ID'),
        'timezone': os.getenv('TIMEZONE', 'America/Mexico_City'),
        'unlock_hour': int(os.getenv('UNLOCK_HOUR', '18')),
        'lock_hour': int(os.getenv('LOCK_HOUR', '22')),
        'script_dir': script_dir
    }

    if not config['api_key']:
        logger.error("❌ NEXTDNS_API_KEY not configured")
        sys.exit(1)

    if not config['profile_id']:
        logger.error("❌ NEXTDNS_PROFILE_ID not configured")
        sys.exit(1)

    return config


def main():
    if len(sys.argv) < 2:
        print("Usage: nextdns_blocker.py [sync|status|block|unblock]")
        print("")
        print("Commands:")
        print("  sync    - Sync domains based on schedule configuration (recommended)")
        print("  status  - Show current status of all domains")
        print("  block   - Force block all domains (ignores schedules)")
        print("  unblock - Force unblock all domains (ignores schedules)")
        sys.exit(1)

    action = sys.argv[1].lower()
    config = load_config()
    blocker = NextDNSBlocker(config['api_key'], config['profile_id'])
    domain_configs = load_domain_configs(config['script_dir'])

    logger.info(f"=== NextDNS Blocker - Action: {action.upper()} ===")

    if action == "sync":
        # Sync command: syncs domains based on their schedules
        evaluator = ScheduleEvaluator(config['timezone'])

        logger.info(f"Synchronizing {len(domain_configs)} domain(s) based on schedules...")

        all_success = True
        blocked_count = 0
        unblocked_count = 0

        for domain_config in domain_configs:
            domain = domain_config['domain']
            schedule = domain_config.get('schedule')

            # Determine desired state
            should_block = evaluator.should_be_blocked(schedule)

            # Check current state
            is_blocked = blocker.find_domain_in_denylist(domain) is not None

            # Sync state if needed
            if should_block and not is_blocked:
                logger.info(f"Domain '{domain}' should be blocked (outside available hours)")
                success = blocker.block_domain(domain)
                if success:
                    blocked_count += 1
                else:
                    all_success = False

            elif not should_block and is_blocked:
                logger.info(f"Domain '{domain}' should be unblocked (within available hours)")
                success = blocker.unblock_domain(domain)
                if success:
                    unblocked_count += 1
                else:
                    all_success = False

            else:
                state = "blocked" if is_blocked else "unblocked"
                logger.info(f"Domain '{domain}' already in correct state ({state})")

        logger.info(f"Sync complete: {blocked_count} blocked, {unblocked_count} unblocked")
        sys.exit(0 if all_success else 1)

    elif action == "status":
        print(f"\nChecking {len(domain_configs)} domain(s):\n")
        for domain_config in domain_configs:
            domain = domain_config['domain']
            domain_id = blocker.find_domain_in_denylist(domain)
            if domain_id:
                print(f"  🔒 BLOCKED   - {domain}")
            else:
                print(f"  🔓 UNBLOCKED - {domain}")
        print("")
        sys.exit(0)

    elif action == "block":
        logger.warning("Force blocking all domains (ignoring schedules)")
        all_success = True
        for domain_config in domain_configs:
            domain = domain_config['domain']
            success = blocker.block_domain(domain)
            if not success:
                all_success = False
        sys.exit(0 if all_success else 1)

    elif action == "unblock":
        logger.warning("Force unblocking all domains (ignoring schedules)")
        all_success = True
        for domain_config in domain_configs:
            domain = domain_config['domain']
            success = blocker.unblock_domain(domain)
            if not success:
                all_success = False
        sys.exit(0 if all_success else 1)

    else:
        logger.error(f"Unknown action: {action}")
        print("Usage: nextdns_blocker.py [sync|status|block|unblock]")
        sys.exit(1)


if __name__ == "__main__":
    main()
