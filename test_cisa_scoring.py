import sys
sys.path.insert(0, '.')
from significance_filter import detect_category, compute_significance_score

# Simulate a CISA item
cisa_item = {
    "title": "Sangoma FreePBX OS Command Injection Vulnerability",
    "summary": "CVE-2024-12345 allows remote code execution",
    "source": "CISA KEV",
    "source_name": "CISA KEV",
    "published": "2026-02-03T00:00:00+00:00"
}

print("Item:", cisa_item)
print("Category:", detect_category(cisa_item))
score = compute_significance_score(cisa_item)
print("Score:", score)

# Also test with source_id as source
cisa_item2 = {
    "title": "Sangoma FreePBX OS Command Injection Vulnerability",
    "summary": "CVE-2024-12345 allows remote code execution",
    "source": "cisa_kev",
    "source_name": "CISA KEV",
    "published": "2026-02-03T00:00:00+00:00"
}
print("\nItem2:", cisa_item2)
print("Category2:", detect_category(cisa_item2))
score2 = compute_significance_score(cisa_item2)
print("Score2:", score2)
