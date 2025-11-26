#!/usr/bin/env python3
"""NextDNS Domain Controller"""

import os, sys, logging, json
from typing import Optional, Dict, Any, List
from datetime import datetime, time
import requests, pytz

# Protected config
NUCLEAR_DOMAINS = ["my.nextdns.io"]
LOG_DIR = os.path.expanduser("~/.local/share/nextdns-audit/logs")
os.makedirs(LOG_DIR, exist_ok=True)
API_URL = "https://api.nextdns.io"

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler(os.path.join(LOG_DIR, 'app.log')), logging.StreamHandler()])
logger = logging.getLogger(__name__)

def audit_log(action: str, detail: str = ""):
    with open(os.path.join(LOG_DIR, 'audit.log'), 'a') as f:
        f.write(f"{datetime.now().isoformat()} | {action} | {detail}\n")
    logger.info(f"Audit: {action}")


class NextDNSClient:
    def __init__(self, api_key: str, profile_id: str):
        self.profile_id = profile_id
        self.headers = {"X-Api-Key": api_key, "Content-Type": "application/json"}

    def request(self, method: str, endpoint: str, data: Optional[Dict] = None, retries: int = 2) -> Optional[Dict[str, Any]]:
        url = f"{API_URL}{endpoint}"
        for attempt in range(retries + 1):
            try:
                if method == "GET": r = requests.get(url, headers=self.headers, timeout=10)
                elif method == "POST": r = requests.post(url, headers=self.headers, json=data, timeout=10)
                elif method == "DELETE": r = requests.delete(url, headers=self.headers, timeout=10)
                else: return None
                r.raise_for_status()
                return r.json() if r.text else {"success": True}
            except requests.exceptions.Timeout:
                if attempt < retries:
                    logger.warning(f"Timeout, retry {attempt + 1}/{retries}")
                    continue
                logger.error(f"API timeout after {retries} retries")
                return None
            except requests.exceptions.RequestException as e:
                logger.error(f"API error: {e}")
                return None

    def get_denylist(self) -> Optional[list]:
        r = self.request("GET", f"/profiles/{self.profile_id}/denylist")
        return r.get("data") if r and "data" in r else None

    def find_domain(self, domain: str) -> Optional[str]:
        denylist = self.get_denylist()
        if denylist is None: return None
        for entry in denylist:
            if entry.get("id") == domain: return entry.get("id")
        return None

    def block(self, domain: str) -> bool:
        if self.find_domain(domain): return True
        r = self.request("POST", f"/profiles/{self.profile_id}/denylist", {"id": domain, "active": True})
        if r: logger.info(f"Blocked: {domain}")
        return r is not None

    def unblock(self, domain: str) -> bool:
        domain_id = self.find_domain(domain)
        if not domain_id: return True
        r = self.request("DELETE", f"/profiles/{self.profile_id}/denylist/{domain_id}")
        if r is not None: logger.info(f"Unblocked: {domain}")
        return r is not None


class ScheduleEvaluator:
    DAYS = {'monday': 0, 'tuesday': 1, 'wednesday': 2, 'thursday': 3, 'friday': 4, 'saturday': 5, 'sunday': 6}

    def __init__(self, timezone: str = 'America/Mexico_City'):
        try: self.tz = pytz.timezone(timezone)
        except pytz.UnknownTimeZoneError: raise ValueError(f"Invalid timezone: {timezone}")

    def parse_time(self, time_str: str) -> time:
        if not time_str or ':' not in time_str: raise ValueError(f"Invalid time: {time_str}")
        try:
            h, m = map(int, time_str.split(':'))
            if not (0 <= h <= 23 and 0 <= m <= 59): raise ValueError
            return time(h, m)
        except (ValueError, AttributeError) as e:
            raise ValueError(f"Invalid time: {time_str}") from e

    def is_time_in_range(self, current: time, start: time, end: time) -> bool:
        if start <= end: return start <= current <= end
        return current >= start or current <= end

    def should_block(self, schedule: Dict) -> bool:
        if not schedule or 'available_hours' not in schedule: return True
        now = datetime.now(self.tz)
        current_day, current_time = now.weekday(), now.time()
        for block in schedule['available_hours']:
            try: days = [self.DAYS[d.lower()] for d in block.get('days', [])]
            except KeyError: return True
            if current_day not in days: continue
            for time_range in block.get('time_ranges', []):
                try:
                    if self.is_time_in_range(current_time, self.parse_time(time_range['start']), self.parse_time(time_range['end'])): return False
                except (KeyError, ValueError): return True
        return True


def validate_domain_config(config: Dict, index: int) -> List[str]:
    errors = []
    if 'domain' not in config: return [f"#{index}: Missing domain"]
    domain = config['domain']
    if not domain or not domain.strip(): return [f"#{index}: Empty domain"]
    schedule = config.get('schedule')
    if schedule is None: return errors
    if not isinstance(schedule, dict): return [f"'{domain}': schedule must be dict"]
    if 'available_hours' not in schedule: return errors
    hours = schedule['available_hours']
    if not isinstance(hours, list): return [f"'{domain}': available_hours must be list"]
    valid_days = {'monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday'}
    for block in hours:
        if not isinstance(block, dict): continue
        for day in block.get('days', []):
            if isinstance(day, str) and day.lower() not in valid_days:
                errors.append(f"'{domain}': invalid day '{day}'")
        for time_range in block.get('time_ranges', []):
            if not isinstance(time_range, dict): continue
            for key in ['start', 'end']:
                if key not in time_range: errors.append(f"'{domain}': missing '{key}'")
    return errors


def load_domains(script_dir: str, domains_url: Optional[str] = None) -> List[Dict]:
    config = None

    if domains_url:
        try:
            r = requests.get(domains_url, timeout=10)
            r.raise_for_status()
            config = r.json()
            logger.info(f"Loaded domains from URL: {domains_url}")
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to load from URL: {e}")
            sys.exit(1)
        except json.JSONDecodeError as e:
            logger.error(f"JSON error from URL: {e}")
            sys.exit(1)
    else:
        json_file = os.path.join(script_dir, 'domains.json')
        if not os.path.exists(json_file):
            logger.error(f"Config not found: {json_file}")
            sys.exit(1)
        try:
            with open(json_file, 'r') as f:
                config = json.load(f)
            logger.info("Loaded domains from local file")
        except json.JSONDecodeError as e:
            logger.error(f"JSON error: {e}")
            sys.exit(1)

    domains = config.get('domains', [])
    if not domains:
        logger.error("No domains")
        sys.exit(1)
    errors = []
    for i, d in enumerate(domains):
        errors.extend(validate_domain_config(d, i))
    if errors:
        for e in errors:
            logger.error(e)
        sys.exit(1)
    return domains


def load_config() -> Dict[str, str]:
    script_dir = os.path.dirname(os.path.abspath(__file__))
    env_file = os.path.join(script_dir, '.env')
    if os.path.exists(env_file):
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
        'domains_url': os.getenv('DOMAINS_URL'),
        'script_dir': script_dir
    }
    if not config['api_key']: logger.error("No API key"); sys.exit(1)
    if not config['profile_id']: logger.error("No profile ID"); sys.exit(1)
    return config


def main():
    if len(sys.argv) < 2:
        print("Usage: [sync|status]")
        sys.exit(1)

    action = sys.argv[1].lower()

    if action in ["unblock", "disable", "remove", "delete", "off"]:
        audit_log(f"BLOCKED_CMD_{action.upper()}", f"Attempted: {action}")
        print(f"\n  error: '{action}' is not available\n")
        sys.exit(1)

    config = load_config()
    client = NextDNSClient(config['api_key'], config['profile_id'])
    domains = load_domains(config['script_dir'], config.get('domains_url'))

    if action == "sync":
        try: scheduler = ScheduleEvaluator(config['timezone'])
        except ValueError as e: logger.error(str(e)); sys.exit(1)

        blocked_count, unblocked_count = 0, 0

        # Nuclear domains - always blocked
        for nuclear in NUCLEAR_DOMAINS:
            if not client.find_domain(nuclear):
                audit_log("NUCLEAR_REBLOCK", nuclear)
                if client.block(nuclear): blocked_count += 1

        # Scheduled domains
        for d in domains:
            domain = d['domain']
            if domain in NUCLEAR_DOMAINS: continue
            should_block = scheduler.should_block(d.get('schedule'))
            is_blocked = client.find_domain(domain) is not None
            if should_block and not is_blocked:
                if client.block(domain): blocked_count += 1
            elif not should_block and is_blocked:
                if client.unblock(domain): unblocked_count += 1

        logger.info(f"Done: {blocked_count} blocked, {unblocked_count} unblocked")

    elif action == "status":
        print("\n  protected")
        print("  ---------")
        for nuclear in NUCLEAR_DOMAINS:
            status = "blocked" if client.find_domain(nuclear) else "WARNING"
            print(f"    {nuclear:<30} {status}")
        print("\n  scheduled")
        print("  ---------")
        for d in domains:
            domain = d['domain']
            if domain in NUCLEAR_DOMAINS: continue
            status = "blocked" if client.find_domain(domain) else "open"
            print(f"    {domain:<30} {status}")
        print()

    else:
        audit_log(f"UNKNOWN_{action}", "")
        print("Usage: [sync|status]")
        sys.exit(1)


if __name__ == "__main__":
    main()
