import feedparser
import ssl
import urllib.request
import urllib.error

# Create SSL context that doesn't verify certificates
ssl_context = ssl.create_default_context()
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE

# Monkey-patch feedparser's urlopen
original_urlopen = urllib.request.urlopen

def custom_urlopen(req, timeout=None, cafile=None, capath=None, cadefault=False, context=None):
    # For FDA domain, use our custom SSL context
    if 'fda.gov' in req.full_url:
        context = ssl_context
    return original_urlopen(req, timeout=timeout, cafile=cafile, capath=capath, cadefault=cadefault, context=context)

urllib.request.urlopen = custom_urlopen

try:
    feed = feedparser.parse('https://data.fda.gov/feeds/cfsan/recalls.xml')
    print(f"Success! Found {len(feed.entries)} entries")
    if feed.entries:
        for i, entry in enumerate(feed.entries[:3]):
            print(f"{i}: {entry.title}")
except Exception as e:
    print(f"Error: {e}")
