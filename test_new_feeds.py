import requests
import feedparser
import time
import sys

feeds = [
    # Government & International Orgs
    ('https://www.federalregister.gov/documents/search.rss', 'fedreg', 'Federal Register'),
    ('https://www.dhs.gov/feeds/rss/news', 'dhs', 'DHS News'),
    ('https://www.fbi.gov/news/rss', 'fbi', 'FBI News'),
    ('https://www.cia.gov/rss', 'cia', 'CIA Press Releases'),
    ('https://www.interpol.int/rss', 'interpol', 'INTERPOL News'),
    ('https://www.europol.europa.eu/rss', 'europol', 'Europol News'),
    ('https://www.iaea.org/rss', 'iaea', 'IAEA News'),
    ('https://www.wto.org/rss', 'wto', 'WTO News'),
    ('https://www.oecd.org/rss', 'oecd', 'OECD News'),
    ('https://www.bis.org/rss', 'bis', 'Bank for International Settlements'),
    ('https://www.fsb.org/rss', 'fsb', 'Financial Stability Board'),
    ('https://www.bankofengland.co.uk/rss/news', 'boe', 'Bank of England'),
    ('https://www.ecb.europa.eu/rss', 'ecb', 'European Central Bank'),
    ('https://www.boj.or.jp/en/announcements/release/index.htm/rss', 'boj', 'Bank of Japan'),
    ('https://www.imf.org/en/News/rss', 'imf', 'IMF News'),
    ('https://www.worldbank.org/en/news/rss', 'worldbank', 'World Bank'),
    ('https://www.un.org/rss', 'un', 'UN News'),
    ('https://www.un.org/securitycouncil/rss', 'unsc', 'UN Security Council'),
    ('https://www.nato.int/cps/en/natohq/news.rss', 'nato', 'NATO News'),
    ('https://www.osce.org/rss', 'osce', 'OSCE Press Releases'),
    
    # Scientific Preprints
    ('https://www.biorxiv.org/rss/current', 'biorxiv', 'bioRxiv Preprints'),
    ('https://www.medrxiv.org/rss/current', 'medrxiv', 'medRxiv Preprints'),
    ('https://www.psyarxiv.com/rss/current', 'psyarxiv', 'PsyArXiv Preprints'),
    
    # Corporate & Financial
    ('https://www.nasdaq.com/feed/rssoutbound?category=Economy', 'nasdaq_news', 'NASDAQ News'),
    ('https://www.nyse.com/rss', 'nyse', 'NYSE News'),
    ('https://www.reuters.com/assets/jsonWireNews', 'reuters_json', 'Reuters Wire'),
    
    # Technology Standards
    ('https://www.ietf.org/rfc/rfc-index.xml', 'ietf', 'IETF RFCs'),
    ('https://www.w3.org/News/news.rss', 'w3c', 'W3C News'),
    
    # Health & Safety
    ('https://www.cdc.gov/cdc-info/rss.html', 'cdc', 'CDC News'),
    ('https://www.fda.gov/about-fda/contact-fda/stay-informed/rss-feeds', 'fda', 'FDA RSS'),
    ('https://www.who.int/rss-feeds/news-english.xml', 'who', 'WHO News'),
    
    # Energy & Environment
    ('https://www.energy.gov/rss', 'energy', 'DOE News'),
    ('https://www.epa.gov/newsreleases/search/rss', 'epa', 'EPA News'),
    ('https://www.noaa.gov/rss', 'noaa', 'NOAA News'),
    
    # Transportation
    ('https://www.faa.gov/newsroom/feed', 'faa', 'FAA News'),
    ('https://www.ntsb.gov/news/rss.xml', 'ntsb', 'NTSB News'),
    ('https://www.icao.int/rss', 'icao', 'ICAO News'),
    ('https://www.imo.org/rss', 'imo', 'IMO News'),
]

def test_feed(url, source_id, source_name):
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (compatible; DeepSeek-News-Monitor/1.0)'}
        response = requests.get(url, headers=headers, timeout=15)
        if response.status_code == 200:
            feed = feedparser.parse(response.content)
            if feed.bozo and feed.bozo_exception:
                print(f"{source_name:30} {source_id:20} ERROR: {feed.bozo_exception}")
                return False
            print(f"{source_name:30} {source_id:20} OK - {len(feed.entries)} entries")
            if len(feed.entries) > 0:
                for i, entry in enumerate(feed.entries[:2]):
                    title = entry.get('title', 'No title')[:70]
                    date = entry.get('published', entry.get('updated', 'No date'))[:30]
                    print(f"    {i+1}. {title}")
                    print(f"       {date}")
            return True
        else:
            print(f"{source_name:30} {source_id:20} HTTP {response.status_code}")
            return False
    except Exception as e:
        print(f"{source_name:30} {source_id:20} EXCEPTION: {e}")
        return False

if __name__ == '__main__':
    print("Testing new RSS feeds...")
    print("="*80)
    working = []
    for url, sid, name in feeds:
        if test_feed(url, sid, name):
            working.append((url, sid, name))
        time.sleep(0.5)
    print("\n" + "="*80)
    print(f"Working feeds: {len(working)}/{len(feeds)}")
    print("\nWorking feed list:")
    for url, sid, name in working:
        print(f'            (\"{url}\", \"{sid}\", \"{name}\"),')
