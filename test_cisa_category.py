import sys
sys.path.insert(0, '.')
from significance_filter import detect_category

# Test CISA KEV item
item = {
    "source": "CISA KEV",
    "source_name": "CISA Known Exploited Vulnerabilities"
}
print("CISA category:", detect_category(item))

# Test defense item
item2 = {
    "source": "US Department of Defense News",
    "source_name": "DoD News"
}
print("Defense category:", detect_category(item2))

# Test government item
item3 = {
    "source": "FDA Recalls",
    "source_name": "FDA Recalls"
}
print("FDA category:", detect_category(item3))
