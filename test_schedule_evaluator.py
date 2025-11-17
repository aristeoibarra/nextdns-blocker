#!/usr/bin/env python3
"""
Test script for ScheduleEvaluator edge cases
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from nextdns_blocker import ScheduleEvaluator
from datetime import time

def test_parse_time():
    """Test time parsing with various inputs"""
    evaluator = ScheduleEvaluator('UTC')

    test_cases = [
        ("09:00", True, None),
        ("23:59", True, None),
        ("00:00", True, None),
        ("25:00", False, "Invalid hour"),
        ("12:60", False, "Invalid minute"),
        ("12:99", False, "Invalid minute"),
        ("-1:00", False, "Negative hour"),
        ("12:-1", False, "Negative minute"),
        ("12:5", True, None),  # Should this be "12:05"?
        ("9:30", True, None),  # Single digit hour
        ("12", False, "Missing colon"),
        ("12:30:45", False, "Too many parts"),
        ("", False, "Empty string"),
        ("abc:def", False, "Non-numeric"),
    ]

    print("Testing _parse_time():")
    for time_str, should_pass, expected_error in test_cases:
        try:
            result = evaluator._parse_time(time_str)
            if should_pass:
                print(f"  ✓ '{time_str}' -> {result}")
            else:
                print(f"  ⚠️ '{time_str}' -> {result} (expected to fail: {expected_error})")
        except Exception as e:
            if not should_pass:
                print(f"  ✓ '{time_str}' -> Failed as expected ({type(e).__name__})")
            else:
                print(f"  ❌ '{time_str}' -> Unexpected failure: {e}")
    print()

def test_time_range():
    """Test time range checking"""
    evaluator = ScheduleEvaluator('UTC')

    test_cases = [
        # (current, start, end, expected_result, description)
        (time(10, 0), time(9, 0), time(17, 0), True, "Within normal range"),
        (time(8, 0), time(9, 0), time(17, 0), False, "Before normal range"),
        (time(18, 0), time(9, 0), time(17, 0), False, "After normal range"),
        (time(9, 0), time(9, 0), time(17, 0), True, "Exactly at start"),
        (time(17, 0), time(9, 0), time(17, 0), True, "Exactly at end"),
        (time(23, 0), time(22, 0), time(2, 0), True, "Midnight crossing - before midnight"),
        (time(1, 0), time(22, 0), time(2, 0), True, "Midnight crossing - after midnight"),
        (time(12, 0), time(22, 0), time(2, 0), False, "Midnight crossing - outside range"),
        (time(0, 0), time(22, 0), time(2, 0), True, "Midnight crossing - exactly midnight"),
    ]

    print("Testing _is_time_in_range():")
    for current, start, end, expected, description in test_cases:
        result = evaluator._is_time_in_range(current, start, end)
        status = "✓" if result == expected else "❌"
        print(f"  {status} {description}: current={current}, range={start}-{end}, result={result}")
    print()

def test_schedule_config():
    """Test schedule configuration edge cases"""
    evaluator = ScheduleEvaluator('UTC')

    test_cases = [
        (None, True, "Null schedule"),
        ({}, True, "Empty dict"),
        ({"available_hours": []}, True, "Empty available_hours"),
        ({"available_hours": [{}]}, True, "Empty schedule block"),
        ({"available_hours": [{"days": []}]}, True, "Empty days list"),
        ({"available_hours": [{"days": ["monday"]}]}, True, "No time_ranges"),
        ({"available_hours": [{"time_ranges": []}]}, True, "No days"),
    ]

    print("Testing should_be_blocked() with edge cases:")
    for config, should_block, description in test_cases:
        try:
            result = evaluator.should_be_blocked(config)
            status = "✓" if result == should_block else "⚠️"
            print(f"  {status} {description}: blocked={result}")
        except Exception as e:
            print(f"  ❌ {description}: Error - {e}")
    print()

def test_invalid_day_names():
    """Test invalid day names"""
    evaluator = ScheduleEvaluator('UTC')

    test_cases = [
        (["Monday"], "Capitalized day name"),
        (["MONDAY"], "Uppercase day name"),
        (["mon"], "Abbreviated day name"),
        (["Lunes"], "Spanish day name"),
        (["invalidday"], "Completely invalid day"),
        ([""], "Empty string day"),
    ]

    print("Testing invalid day names:")
    for days, description in test_cases:
        config = {
            "available_hours": [{
                "days": days,
                "time_ranges": [{"start": "09:00", "end": "17:00"}]
            }]
        }
        try:
            result = evaluator.should_be_blocked(config)
            print(f"  ⚠️ {description}: No error raised, result={result}")
        except Exception as e:
            print(f"  ✓ {description}: Error caught - {type(e).__name__}")
    print()

if __name__ == "__main__":
    print("=" * 60)
    print("ScheduleEvaluator Edge Case Testing")
    print("=" * 60)
    print()

    test_parse_time()
    test_time_range()
    test_schedule_config()
    test_invalid_day_names()

    print("=" * 60)
    print("Testing complete!")
    print("=" * 60)
