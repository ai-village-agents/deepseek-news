import sys
sys.path.insert(0, '.')
import major_news_config
from significance_filter import detect_category, compute_significance_score

# Simulate exactly what monitor does
source_id = "cisa_kev"
source_name = "CISA KEV"
title = "Sangoma FreePBX OS Command Injection Vulnerability"
summary = "CVE-2024-12345 allows remote code execution"
published_time = "2026-02-03T00:00:00+00:00"

# Item dict as created by calculate_significance
item = {
    "title": title,
    "summary": summary,
    "source": source_id,  # This is what monitor uses
    "published": published_time
}

print("Item dict:", item)
print("Category:", detect_category(item))

# Also test with source_name included
item2 = {
    "title": title,
    "summary": summary,
    "source": source_name,
    "source_name": source_name,
    "published": published_time
}
print("\nItem2 with source_name:", item2)
print("Category2:", detect_category(item2))

# Compute scores
config = major_news_config.MAJOR_NEWS_CONFIG
print("\nConfig weights:", config.get("weights", {}).get("cisa", "NOT FOUND"))
score = compute_significance_score(item, config)
print("Score:", score)
score2 = compute_significance_score(item2, config)
print("Score2:", score2)

# Let's manually compute
from significance_filter import detect_category, compute_significance_score
import copy
config_copy = copy.deepcopy(config)
print("\nConfig copy weights:", config_copy.get("weights", {}))
