#!/usr/bin/env python3
import sys
sys.path.append('.')

from significance_filter import detect_category

test_items = [
    {
        'title': 'CISA Adds Two Known Exploited Vulnerabilities - CVE-2024-12345 and CVE-2024-67890',
        'description': 'The Cybersecurity and Infrastructure Security Agency (CISA) has added two new vulnerabilities to its Known Exploited Vulnerabilities (KEV) catalog: CVE-2024-12345 and CVE-2024-67890.',
        'source_id': 'cisa_kev'
    },
    {
        'title': 'CISA Updates Known Exploited Vulnerabilities Catalog',
        'description': 'Cybersecurity advisory about new KEV entries.',
        'source_id': 'rss'
    },
    {
        'title': 'Microsoft Patch Tuesday includes fixes for known exploited vulnerabilities',
        'description': 'CISA warns about these vulnerabilities being actively exploited.',
        'source_id': 'rss'
    }
]

for i, item in enumerate(test_items):
    category = detect_category(item)
    print(f"Test item {i+1}:")
    print(f"  Title: {item['title'][:60]}...")
    print(f"  Source ID: {item.get('source_id', 'N/A')}")
    print(f"  Detected category: {category}")
    print()
