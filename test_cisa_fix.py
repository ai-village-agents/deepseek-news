import sys
sys.path.insert(0, '.')

from monitor_international import InternationalNewsMonitor

monitor = InternationalNewsMonitor()

# Test CISA KEV vulnerability
cisa_title = "GitLab Community and Enterprise Editions Server-Side Request Forgery (SSRF) Vulnerability"
cisa_summary = "GitLab Community and Enterprise Editions contain a server-side request forgery vulnerability..."

result = monitor.check_mainstream_coverage(cisa_title, cisa_summary)
print(f"CISA KEV title mainstream check: {result} (should be False)")

# Test BBC story
bbc_title = "BBC joins Colombian commandos fighting"
bbc_summary = ""
result = monitor.check_mainstream_coverage(bbc_title, bbc_summary)
print(f"BBC title mainstream check: {result} (should be True)")

# Test SolarWinds
sw_title = "SolarWinds hack investigation reveals new details"
sw_summary = ""
result = monitor.check_mainstream_coverage(sw_title, sw_summary)
print(f"SolarWinds title mainstream check: {result} (should be False)")

# Test partial match false positive
partial_title = "Enterprise edition software update"
partial_summary = ""
result = monitor.check_mainstream_coverage(partial_title, partial_summary)
print(f"Partial match title mainstream check: {result} (should be False)")
