#!/usr/bin/env python3
"""
Test script for JSON validation
"""
import sys
import os
import json
sys.path.insert(0, os.path.dirname(__file__))

from nextdns_blocker import validate_domain_config

def test_validation():
    """Test validation with invalid configurations"""

    print("=" * 60)
    print("Testing JSON Validation")
    print("=" * 60)
    print()

    # Test case 1: Invalid day name
    print("Test 1: Invalid day name ('mon')")
    config1 = {
        "domain": "test1.com",
        "schedule": {
            "available_hours": [{
                "days": ["mon", "tuesday"],
                "time_ranges": [{"start": "09:00", "end": "17:00"}]
            }]
        }
    }
    errors1 = validate_domain_config(config1, 0)
    if errors1:
        print(f"  ✓ Validation caught errors:")
        for err in errors1:
            print(f"    - {err}")
    else:
        print(f"  ❌ No errors found (should have found invalid day)")
    print()

    # Test case 2: Invalid time format
    print("Test 2: Invalid time format ('25:00')")
    config2 = {
        "domain": "test2.com",
        "schedule": {
            "available_hours": [{
                "days": ["monday"],
                "time_ranges": [{"start": "25:00", "end": "17:00"}]
            }]
        }
    }
    errors2 = validate_domain_config(config2, 1)
    if errors2:
        print(f"  ✓ Validation caught errors:")
        for err in errors2:
            print(f"    - {err}")
    else:
        print(f"  ❌ No errors found (should have found invalid time)")
    print()

    # Test case 3: Missing domain field
    print("Test 3: Missing 'domain' field")
    config3 = {
        "schedule": {
            "available_hours": []
        }
    }
    errors3 = validate_domain_config(config3, 2)
    if errors3:
        print(f"  ✓ Validation caught errors:")
        for err in errors3:
            print(f"    - {err}")
    else:
        print(f"  ❌ No errors found (should have found missing domain)")
    print()

    # Test case 4: Valid configuration
    print("Test 4: Valid configuration")
    config4 = {
        "domain": "valid.com",
        "schedule": {
            "available_hours": [{
                "days": ["monday", "tuesday"],
                "time_ranges": [{"start": "09:00", "end": "17:00"}]
            }]
        }
    }
    errors4 = validate_domain_config(config4, 3)
    if errors4:
        print(f"  ❌ Unexpected errors:")
        for err in errors4:
            print(f"    - {err}")
    else:
        print(f"  ✓ No errors (correct)")
    print()

    # Test case 5: Multiple errors in one config
    print("Test 5: Multiple errors (invalid day + invalid time)")
    config5 = {
        "domain": "multi-error.com",
        "schedule": {
            "available_hours": [{
                "days": ["Monday", "mon"],
                "time_ranges": [
                    {"start": "25:00", "end": "17:00"},
                    {"start": "09:00", "end": "30:00"}
                ]
            }]
        }
    }
    errors5 = validate_domain_config(config5, 4)
    if errors5:
        print(f"  ✓ Validation caught {len(errors5)} error(s):")
        for err in errors5:
            print(f"    - {err}")
    else:
        print(f"  ❌ No errors found (should have found multiple errors)")
    print()

    print("=" * 60)
    print("Validation testing complete!")
    print("=" * 60)

if __name__ == "__main__":
    test_validation()
