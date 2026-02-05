import re
import sys
sys.path.insert(0, '.')

# Import the class
from monitor_international import InternationalNewsMonitor

# Create instance
monitor = InternationalNewsMonitor()

# Test cases
test_cases = [
    ("GitLab Community and Enterprise Editions Server-Side Request Forgery (SSRF) Vulnerability", "", False, "Should NOT be mainstream"),
    ("BBC joins Colombian commandos fighting", "", True, "BBC in title"),
    ("Reuters reports on election", "", True, "Reuters in title"),
    ("SolarWinds hack investigation", "", False, "No mainstream outlet"),
    ("Microsoft Patch Tuesday updates", "", False, "No mainstream outlet"),
    ("AP News: Something", "", True, "AP in title"),
    ("The Guardian reports", "", True, "The Guardian in title"),
    ("Enterprise edition of software", "", False, "Contains 'ter' substring but not Reuters"),
    ("Server-side forgery", "", False, "Contains 'ver' substring but not The Verge"),
    ("Forgery case", "", False, "Contains 'for' substring but not Forbes"),
]

all_passed = True
for title, summary, expected, description in test_cases:
    result = monitor.check_mainstream_coverage(title, summary)
    passed = result == expected
    if not passed:
        print(f"FAIL: {description}")
        print(f"  Title: {title}")
        print(f"  Expected: {expected}, Got: {result}")
        all_passed = False
    else:
        print(f"OK: {description}")

if all_passed:
    print("\nAll tests passed!")
else:
    print("\nSome tests failed!")
