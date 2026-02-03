"""
Major World News Configuration for DeepSeek-V3.2 News Monitor
Focus on high-impact news sources as per Adam's guidance:
- Major world news, not small GitHub repos
- Difficulty and eventual coverage volume matter
- Quality over quantity
"""

MAJOR_NEWS_CONFIG = {
    "threshold": 7.0,  # Higher threshold for truly significant news
    "archive_threshold": 5.0,
    "base_score": 1.0,
    "weights": {
        # HIGH IMPACT GOVERNMENT/REGULATORY
        "sec": 8.0,  # SEC filings for major M&A, bankruptcies
        "fda": 7.5,  # FDA approvals/recalls
        "government": 6.0,
        "regulatory": 6.0,
        "nasa": 5.0,
        "earthquake": 6.0,  # Only significant earthquakes
        
        # CORPORATE NEWS (major companies)
        "corporate": 5.0,
        
        # TECH/SECURITY (major vulnerabilities)
        "security": 6.0,
        "cisa": 7.0,
        
        # LOWER PRIORITY - GitHub trending repos should rarely pass
        "github_trending": 1.0,  # Severely reduced from 4.0
        "github_release": 1.5,
        "arxiv": 2.0,  # Reduced - research papers rarely break as world news
        "hackernews": 2.0,
        "nasdaq_halt": 4.0,  # Keep moderate - financial halts can be significant
    },
    
    # Earthquake configuration - focus on major events only
    "earthquake": {
        "min_magnitude": 5.0,  # Only report magnitude 5.0+
        "major_magnitude": 6.5,  # Major earthquakes
        "magnitude_scale": 1.2,
        "major_bonus": 3.0,
    },
    
    # GitHub trending - make it very hard to pass
    "github_trending": {
        "recency_bonus_hours": 24,
        "recency_bonus_max": 1.0,
        "star_bonuses": {
            "10000": 2.0,    # 10k+ stars might be newsworthy
            "5000": 1.0,
            "1000": 0.5,
            "500": 0.2,
            # No bonus for <500 stars
        },
        "topics_bonus": 0.1,
        "created_today_bonus": 0.5,
    },
    
    # arXiv - only breakthrough papers
    "arxiv": {
        "priority_keywords": [
            "breakthrough", "state of the art", "sota", "record",
            "first", "novel", "transformative", "revolutionary",
            "artificial general intelligence", "agi", "gpt-5", "gemini 3",
            "claude 4", "major advance", "paradigm shift"
        ],
        "keyword_bonus": 2.0,
        "title_length_bonus": 0.3,
    },
    
    # NASDAQ halts - only LUDP (news pending) and recent
    "nasdaq_halt": {
        "ludp_bonus": 3.0,
        "recent_bonus_5min": 2.0,
        "recent_bonus_10min": 1.0,
    },
    
    "caps": {
        "min_score": 0.0,
        "max_score": 10.0
    }
}

# Additional high-impact sources to add
HIGH_IMPACT_SOURCES = [
    # Cybersecurity
    ("https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json", "cisa_kev", "CISA KEV"),
    
    # Transportation Safety
    ("https://www.nhtsa.gov/api/reports/recalls", "nhtsa_recalls", "NHTSA Recalls"),
    
    # Aviation
    ("https://www.faa.gov/newsroom/feed", "faa_news", "FAA News"),
    
    # International News (wire services)
    ("http://feeds.reuters.com/reuters/topNews", "reuters_top", "Reuters Top News"),
    ("https://rss.nytimes.com/services/xml/rss/nyt/HomePage.xml", "nyt_home", "NYT Home"),
    
    # Business/Financial
    ("https://www.wsj.com/xml/rss/3_7085.xml", "wsj_world", "WSJ World News"),
    
    # Health/Emergency
    ("https://www.cdc.gov/cdc-info/rss.html", "cdc_rss", "CDC News"),
    ("https://www.who.int/rss-feeds/news-english.xml", "who_news", "WHO News"),
]

# Keywords that indicate mainstream coverage (to filter out)
MAINSTREAM_KEYWORDS = [
    "reuters", "ap news", "associated press", "bloomberg", "cnn", "bbc",
    "the new york times", "washington post", "wall street journal",
    "fox news", "nbc news", "cbs news", "abc news", "usatoday",
    "the guardian", "forbes", "business insider", "techcrunch", "the verge"
]

