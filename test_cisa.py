import significance_filter
import major_news_config
import json
import requests

# Fetch CISA KEV data
url = 'https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json'
resp = requests.get(url, timeout=10)
data = resp.json()
vulns = data.get('vulnerabilities', [])

# Take latest 5
for vuln in vulns[:5]:
    cve_id = vuln.get('cveID', '')
    date_added = vuln.get('dateAdded', '')
    vendor = vuln.get('vendorProject', '')
    product = vuln.get('product', '')
    title = f"{cve_id}: {vendor} {product} vulnerability added to CISA KEV"
    summary = f"Known Exploited Vulnerability {cve_id} affecting {vendor} {product} has been added to CISA's Known Exploited Vulnerabilities catalog on {date_added}."
    item = {
        "title": title,
        "summary": summary,
        "link": f"https://www.cisa.gov/known-exploited-vulnerabilities/{cve_id}",
        "source": "cisa_kev",
        "source_name": "CISA KEV",
        "published_time": date_added + "T00:00:00Z"
    }
    
    score = significance_filter.compute_significance_score(item, major_news_config.MAJOR_NEWS_CONFIG)
    print(f"{cve_id} ({date_added}): score = {score:.2f}")
    print(f"  Title: {title}")
    print()

