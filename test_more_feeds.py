import requests
import feedparser
import time

feeds_to_test = [
    # UN Security Council
    ("https://www.un.org/securitycouncil/content/un-sc-press-releases", "un_sc", "UN Security Council"),
    # IAEA
    ("https://www.iaea.org/newscenter/news/rss", "iaea", "IAEA News"),
    # WHO Emergencies
    ("https://www.who.int/emergencies/disease-outbreak-news/rss.xml", "who_emergencies", "WHO Emergencies"),
    # CDC Outbreaks
    ("https://tools.cdc.gov/api/v2/resources/media/403372.rss", "cdc_outbreaks", "CDC Outbreak News"),
    # European CDC
    ("https://www.ecdc.europa.eu/en/news-events/rss.xml", "ecdc", "ECDC News"),
    # US Treasury (OFAC)
    ("https://home.treasury.gov/news/rss.xml", "treasury", "US Treasury"),
    # Commerce BIS
    ("https://www.bis.doc.gov/index.php/newsroom?format=feed&type=rss", "commerce_bis", "Commerce BIS"),
    # DOJ Press Releases
    ("https://www.justice.gov/feeds/opa/justice-news.xml", "doj", "DOJ Press Releases"),
    # FBI Press Releases
    ("https://www.fbi.gov/feeds/rss/press-releases", "fbi", "FBI Press Releases"),
    # Reuters Africa
    ("http://feeds.reuters.com/reuters/AFRICATopNews", "reuters_africa", "Reuters Africa"),
    # Reuters Asia
    ("http://feeds.reuters.com/reuters/AsiaTopNews", "reuters_asia", "Reuters Asia"),
    # Reuters Europe
    ("http://feeds.reuters.com/reuters/EuropeTopNews", "reuters_europe", "Reuters Europe"),
    # AP Top News
    ("http://hosted.ap.org/lineups/TOPHEADS-rss_2.0.xml", "ap_top", "AP Top News"),
    # Xinhua English
    ("http://www.xinhuanet.com/english/rss/worldrss.xml", "xinhua", "Xinhua World"),
    # African Union
    ("https://au.int/en/rss/latest", "au", "African Union"),
    # ASEAN
    ("https://asean.org/feed/", "asean", "ASEAN News"),
]

for url, source_id, name in feeds_to_test:
    try:
        print(f"\nTesting: {name}")
        response = requests.get(url, timeout=10, headers={'User-Agent': 'Mozilla/5.0'})
        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            feed = feedparser.parse(response.content)
            if feed.bozo:
                print(f"Parse error: {feed.bozo_exception}")
            else:
                print(f"Entries: {len(feed.entries)}")
                if feed.entries:
                    print(f"Latest: {feed.entries[0].title[:80]}...")
        else:
            print(f"HTTP error, content: {response.text[:100]}")
    except Exception as e:
        print(f"Error: {e}")
    time.sleep(0.5)
