import requests
import feedparser
import time

feeds = [
    # Canadian PM / Government
    ("https://pm.gc.ca/en/news/feed", "canada_pm", "Canadian PM News"),
    ("https://www.canada.ca/en/news/feed.xml", "canada_gov", "Canada Government"),
    ("https://www.international.gc.ca/world-monde/news-communiques/index.aspx?lang=eng&view=rss", "canada_global_affairs", "Global Affairs Canada"),
    
    # World Bank
    ("https://www.worldbank.org/en/news/press-release/rss.xml", "world_bank_press", "World Bank Press Releases"),
    ("https://www.worldbank.org/en/news/feature/rss.xml", "world_bank_features", "World Bank Features"),
    ("https://blogs.worldbank.org/all/rss.xml", "world_bank_blogs", "World Bank Blogs"),
    
    # IMF
    ("https://www.imf.org/en/News/RSS", "imf_news", "IMF News"),
    ("https://www.imf.org/en/Publications/RSS", "imf_publications", "IMF Publications"),
    
    # IADB (Inter-American Development Bank)
    ("https://www.iadb.org/en/news/rss", "iadb_news", "IADB News"),
    
    # OECD
    ("https://www.oecd.org/newsroom/rss.xml", "oecd_news", "OECD News"),
    
    # Commonwealth
    ("https://thecommonwealth.org/news/rss.xml", "commonwealth_news", "Commonwealth News"),
    
    # OSCE (already have but check)
    ("https://www.osce.org/rss", "osce", "OSCE Press Releases"),
    
    # OAS (Organization of American States)
    ("https://www.oas.org/en/media_center/rss.asp", "oas_news", "OAS News"),
]

for url, source_id, name in feeds:
    try:
        print(f"\nTesting: {name} ({source_id})")
        print(f"URL: {url}")
        response = requests.get(url, timeout=10)
        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            # Try to parse as RSS
            feed = feedparser.parse(url)
            if feed.bozo:
                print(f"Parse error: {feed.bozo_exception}")
            else:
                print(f"Entries: {len(feed.entries)}")
                if feed.entries:
                    print(f"Latest: {feed.entries[0].title[:80]}...")
        else:
            print(f"HTTP error")
    except Exception as e:
        print(f"Error: {e}")
    time.sleep(0.5)
