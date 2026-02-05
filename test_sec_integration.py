#!/usr/bin/env python3
import logging
logging.basicConfig(level=logging.DEBUG)
import sys
sys.path.append('.')
from monitor_international import InternationalNewsMonitor

monitor = InternationalNewsMonitor()
print('Testing SEC EDGAR batch feed integration...')
try:
    # Force fetch by setting last fetch to None
    monitor.state['last_sec_edgar_fetch'] = None
    entries = monitor.parse_sec_edgar_feed()
    print(f'Got {len(entries)} entries')
    for entry in entries[:5]:
        print(f'  - {entry.get("title")}')
        print(f'    ID: {entry.get("id")}')
        print(f'    Published: {entry.get("published")}')
    # Now test check_rss_feeds integration
    print('\nRunning check_rss_feeds...')
    monitor.check_rss_feeds()
except Exception as e:
    print(f'Error: {e}')
    import traceback
    traceback.print_exc()
