import requests
import feedparser
from urllib.parse import urljoin

court_urls = [
    # ICC
    ("https://www.icc-cpi.int", "/feed/rss"),
    ("https://www.icc-cpi.int", "/rss.xml"),
    ("https://www.icc-cpi.int", "/news/rss"),
    ("https://www.icc-cpi.int", "/news/feed"),
    ("https://www.icc-cpi.int", "/news/rss.xml"),
    # ICJ
    ("https://www.icj-cij.org", "/feed/rss"),
    ("https://www.icj-cij.org", "/rss.xml"),
    ("https://www.icj-cij.org", "/news/rss"),
    ("https://www.icj-cij.org", "/latest/rss"),
    ("https://www.icj-cij.org", "/en/feed"),
    # ECHR
    ("https://www.echr.coe.int", "/feed/rss"),
    ("https://www.echr.coe.int", "/rss.xml"),
    ("https://www.echr.coe.int", "/news/rss"),
    ("https://www.echr.coe.int", "/en/feed"),
    ("https://hudoc.echr.coe.int", "/feed/rss"),
    # ITLOS
    ("https://www.itlos.org", "/feed/rss"),
    ("https://www.itlos.org", "/rss.xml"),
    ("https://www.itlos.org", "/news/rss"),
    ("https://www.itlos.org", "/en/feed"),
]

for base, path in court_urls:
    url = urljoin(base, path)
    try:
        response = requests.get(url, timeout=10, headers={'User-Agent': 'Mozilla/5.0'})
        if response.status_code == 200:
            # Try to parse as feed
            feed = feedparser.parse(response.content)
            if len(feed.entries) > 0 or 'title' in feed.feed:
                print(f"✓ {url} - Status {response.status_code}, Entries: {len(feed.entries)}")
            else:
                print(f"? {url} - Status {response.status_code} but no feed entries")
        else:
            print(f"✗ {url} - Status {response.status_code}")
    except Exception as e:
        print(f"! {url} - Error: {e}")
