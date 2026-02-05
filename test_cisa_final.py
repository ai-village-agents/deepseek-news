#!/usr/bin/env python3
import sys
sys.path.append('.')

from significance_filter import detect_category, compute_significance_score, DEFAULT_CONFIG

# Test CISA item with proper fields as parse_json_feed would create
cisa_item = {
    'title': 'CISA Adds Two Known Exploited Vulnerabilities - CVE-2024-12345 and CVE-2024-67890',
    'description': 'The Cybersecurity and Infrastructure Security Agency (CISA) has added two new vulnerabilities to its Known Exploited Vulnerabilities (KEV) catalog: CVE-2024-12345 and CVE-2024-67890.',
    'link': 'https://www.cisa.gov/known-exploited-vulnerabilities',
    'published': '2026-02-04T00:00:00Z',
    'source': 'CISA KEV',
    'source_name': 'CISA KEV',
    'source_id': 'cisa_kev'
}

print("Testing CISA item detection...")
print(f"Item fields: {list(cisa_item.keys())}")
category = detect_category(cisa_item)
print(f"Detected category: {category}")

score = compute_significance_score(cisa_item, DEFAULT_CONFIG)
print(f"\nCISA item score: {score}")
print(f"Should publish (score >= 7.0): {score >= 7.0}")

# Check weight mapping
print(f"\nConfig weights: {DEFAULT_CONFIG.get('weights', {})}")
print(f"Weight for 'cisa': {DEFAULT_CONFIG.get('weights', {}).get('cisa', 'NOT FOUND')}")

# Also test without source fields (should still work via source_id)
cisa_item2 = {
    'title': 'CISA KEV Update',
    'description': 'New vulnerabilities added.',
    'source_id': 'cisa_kev'
}
category2 = detect_category(cisa_item2)
print(f"\nTest 2 (only source_id): category = {category2}")
