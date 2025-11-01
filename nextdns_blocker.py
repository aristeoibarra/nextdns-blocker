#!/usr/bin/env python3
"""
NextDNS Config Blocker
Blocks/unblocks access to my.nextdns.io using NextDNS API
"""

import os
import sys
import logging
from typing import Optional, Dict, Any
import requests

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


def load_domains(script_dir: str) -> list:
    """Loads domains from domains.txt file"""
    domains_file = os.path.join(script_dir, 'domains.txt')
    domains = []

    if not os.path.exists(domains_file):
        logger.warning(f"domains.txt not found, using default: my.nextdns.io")
        return ["my.nextdns.io"]

    with open(domains_file, 'r') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#'):
                domains.append(line)

    if not domains:
        logger.warning("No domains found in domains.txt, using default: my.nextdns.io")
        return ["my.nextdns.io"]

    logger.info(f"Loaded {len(domains)} domain(s) from domains.txt")
    return domains


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
        print("Usage: nextdns_blocker.py [block|unblock|status]")
        sys.exit(1)

    action = sys.argv[1].lower()
    config = load_config()
    blocker = NextDNSBlocker(config['api_key'], config['profile_id'])
    domains = load_domains(config['script_dir'])

    logger.info(f"=== NextDNS Blocker - Action: {action.upper()} ===")

    if action == "block":
        all_success = True
        for domain in domains:
            success = blocker.block_domain(domain)
            if not success:
                all_success = False
        sys.exit(0 if all_success else 1)

    elif action == "unblock":
        all_success = True
        for domain in domains:
            success = blocker.unblock_domain(domain)
            if not success:
                all_success = False
        sys.exit(0 if all_success else 1)

    elif action == "status":
        print(f"\nChecking {len(domains)} domain(s):\n")
        for domain in domains:
            domain_id = blocker.find_domain_in_denylist(domain)
            if domain_id:
                print(f"  🔒 BLOCKED   - {domain}")
            else:
                print(f"  🔓 UNBLOCKED - {domain}")
        print("")
        sys.exit(0)

    else:
        logger.error(f"Unknown action: {action}")
        print("Usage: nextdns_blocker.py [block|unblock|status]")
        sys.exit(1)


if __name__ == "__main__":
    main()
