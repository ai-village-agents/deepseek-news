#!/usr/bin/env python3
import json
import sys
sys.path.append('.')

from significance_filter import compute_significance_score, DEFAULT_CONFIG

# Test CISA item
cisa_item = {
    'title': 'CISA Adds Two Known Exploited Vulnerabilities - CVE-2024-12345 and CVE-2024-67890',
    'description': 'The Cybersecurity and Infrastructure Security Agency (CISA) has added two new vulnerabilities to its Known Exploited Vulnerabilities (KEV) catalog: CVE-2024-12345 and CVE-2024-67890.',
    'link': 'https://www.cisa.gov/known-exploited-vulnerabilities',
    'published': '2026-02-04T00:00:00Z',
    'source_id': 'cisa_kev'
}

print("Testing CISA item scoring...")
score = compute_significance_score(cisa_item, DEFAULT_CONFIG)
print(f"CISA item score: {score}")
print(f"Should publish (score >= 7.0): {score >= 7.0}")

# Test mainstream filter bypass
from monitor_international import InternationalNewsMonitor
monitor = InternationalNewsMonitor()

# Mock the check_mainstream_coverage method
text = cisa_item['title'] + ' ' + cisa_item['description']
is_mainstream = monitor.check_mainstream_coverage(text, source_id='cisa_kev')
print(f"\nMainstream filter check for CISA item (source_id='cisa_kev'): {is_mainstream}")
print("Should be False (CISA should bypass mainstream filter)")
