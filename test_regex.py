import re

def check_mainstream_coverage_new(title: str, summary: str = "", link: str = "") -> bool:
    """Check if news has already been covered by mainstream outlets using word boundaries."""
    combined_text = f"{title} {summary}".lower()
    
    # Mainstream outlet keywords with word boundaries
    mainstream_keywords = [
        "Reuters", "AP", "Associated Press", "Bloomberg", "AFP",
        "CNN", "BBC", "New York Times", "Washington Post", "Wall Street Journal",
        "TechCrunch", "The Verge", "Wired", "Ars Technica", "CNET",
        "Forbes", "Business Insider", "Financial Times", "The Guardian",
        "NPR", "Fox News", "MSNBC", "CBS News", "ABC News", "NBC News"
    ]
    
    # Check for mainstream outlet mentions with word boundaries
    for keyword in mainstream_keywords:
        pattern = r'\b' + re.escape(keyword.lower()) + r'\b'
        if re.search(pattern, combined_text):
            print(f"Found mainstream keyword '{keyword}' in content: {combined_text[:100]}...")
            return True
    
    return False

# Test cases
test_cases = [
    ("GitLab Community and Enterprise Editions Server-Side Request Forgery (SSRF) Vulnerability", ""),
    ("BBC joins Colombian commandos fighting", ""),
    ("Reuters reports on election", ""),
    ("SolarWinds hack investigation", ""),
    ("Microsoft Patch Tuesday updates", ""),
]

for title, summary in test_cases:
    result = check_mainstream_coverage_new(title, summary)
    print(f"Title: {title[:60]}... -> Mainstream: {result}")
