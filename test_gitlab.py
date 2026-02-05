import re

# Exact mainstream keywords from monitor_international.py
mainstream_keywords = [
    "Reuters", "AP", "Associated Press", "Bloomberg", "AFP",
    "CNN", "BBC", "New York Times", "Washington Post", "Wall Street Journal",
    "TechCrunch", "The Verge", "Wired", "Ars Technica", "CNET",
    "Forbes", "Business Insider", "Financial Times", "The Guardian",
    "NPR", "Fox News", "MSNBC", "CBS News", "ABC News", "NBC News"
]

# Test string from CISA KEV
title = "GitLab Community and Enterprise Editions Server-Side Request Forgery (SSRF) Vulnerability"
summary = ""
link = ""

combined_raw = f"{title} {summary}"
combined_text = combined_raw.lower()

print(f"Combined text (lower): {combined_text}")
print("\nChecking each keyword:")

for keyword in mainstream_keywords:
    if keyword.lower() in combined_text:
        idx = combined_text.find(keyword.lower())
        snippet_start = max(0, idx - 40)
        snippet_end = min(len(combined_text), idx + len(keyword) + 40)
        snippet = combined_raw[snippet_start:snippet_end].strip()
        print(f"  MATCHED: '{keyword}' -> snippet: \"{snippet}\"")
    else:
        # Also check substring of keyword in combined_text
        # (maybe partial match?)
        for i in range(len(keyword)):
            for j in range(i+1, len(keyword)+1):
                sub = keyword[i:j].lower()
                if len(sub) >= 3 and sub in combined_text:
                    print(f"  PARTIAL: '{keyword}' contains substring '{sub}' which appears in combined_text")

