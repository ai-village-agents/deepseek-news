import sys
sys.path.insert(0, '.')
from significance_filter import compute_significance_score, detect_category
from major_news_config import MAJOR_NEWS_CONFIG as config

# Test Federal Register item
item = {
    "title": "Celebrating American Greatness With American Motor Racing",
    "summary": "This is a Federal Register document",
    "source": "Federal Register",
    "source_id": "federal_register",
    "published": "2026-02-04T00:00:00+00:00"
}

category = detect_category(item)
print(f"Category detected: {category}")

score = compute_significance_score(item, config)
print(f"Score: {score}")

# Check weight
weight = config.get("weights", {}).get(category, 1.0)
print(f"Weight for {category}: {weight}")

# Also test with source_id detection
item2 = {
    "title": "Test",
    "summary": "Test",
    "source": "Federal Register",
    "published": "2026-02-04T00:00:00+00:00"
}
category2 = detect_category(item2)
print(f"Category without source_id: {category2}")
