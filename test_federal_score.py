from significance_filter import compute_significance_score
from major_news_config import significance_config

# Test Federal Register item
item = {
    "title": "Test Federal Register Document",
    "summary": "This is a test document from the Federal Register",
    "source": "Federal Register",
    "source_id": "federal_register",
    "published": "2026-02-04T00:00:00+00:00"
}

score = compute_significance_score(item, significance_config)
print(f"Score: {score}")

# Check detect_category
from significance_filter import detect_category
category = detect_category(item)
print(f"Category: {category}")

# Check weights
weight = significance_config.get("weights", {}).get(category, 1.0)
print(f"Weight for category '{category}': {weight}")
