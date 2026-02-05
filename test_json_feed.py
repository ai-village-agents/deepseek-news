#!/usr/bin/env python3
import sys
sys.path.append('.')
from monitor_international import InternationalNewsMonitor
import logging
logging.basicConfig(level=logging.DEBUG)
monitor = InternationalNewsMonitor()
print("Testing CISA KEV feed...")
url = "https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json"
print(f"Feed URL: {url}")
print(f"is_json_feed result: {monitor.is_json_feed(url)}")
if monitor.is_json_feed(url):
    entries = monitor.parse_json_feed(url, "cisa_kev", "CISA KEV")
    print(f"Found {len(entries)} entries")
    for entry in entries[:3]:
        print(f"  - {entry.get('title')}")
else:
    print("Feed not recognized as JSON")
