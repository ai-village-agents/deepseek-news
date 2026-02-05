import re

# Exact keyword list from monitor_international.py
mainstream_keywords = [
    "Reuters", "AP", "Associated Press", "Bloomberg", "AFP",
    "CNN", "BBC", "New York Times", "Washington Post", "Wall Street Journal",
    "TechCrunch", "The Verge", "Wired", "Ars Technica", "CNET",
    "Forbes", "Business Insider", "Financial Times", "The Guardian",
    "NPR", "Fox News", "MSNBC", "CBS News", "ABC News", "NBC News"
]

def check_mainstream_coverage_old(title: str, summary: str = "", link: str = "") -> bool:
    combined_text = f"{title} {summary}".lower()
    for keyword in mainstream_keywords:
        if keyword.lower() in combined_text:
            print(f"OLD: Found mainstream keyword '{keyword}' in content")
            return True
    return False

def check_mainstream_coverage_new(title: str, summary: str = "", link: str = "") -> bool:
    combined_text = f"{title} {summary}".lower()
    for keyword in mainstream_keywords:
        pattern = r'\b' + re.escape(keyword.lower()) + r'\b'
        if re.search(pattern, combined_text):
            print(f"NEW: Found mainstream keyword '{keyword}' in content")
            return True
    return False

# Test cases
test_cases = [
    ("GitLab Community and Enterprise Editions Server-Side Request Forgery (SSRF) Vulnerability", ""),
    ("BBC joins Colombian commandos fighting", ""),
    ("Reuters reports on election", ""),
    ("SolarWinds hack investigation", ""),
    ("Microsoft Patch Tuesday updates", ""),
    ("AP News: Something", ""),
    ("The Guardian reports", ""),
]

for title, summary in test_cases:
    old = check_mainstream_coverage_old(title, summary)
    new = check_mainstream_coverage_new(title, summary)
    print(f"Title: {title[:60]}... -> Old: {old}, New: {new}")
