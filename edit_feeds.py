import sys

with open('monitor_international.py', 'r') as f:
    lines = f.readlines()

# Find the line with the closing bracket of feeds list
closing_idx = -1
for i, line in enumerate(lines):
    if line.rstrip() == '        ]' and i > 100:  # after line 100
        closing_idx = i
        break

if closing_idx == -1:
    print("Error: Could not find closing bracket of feeds list")
    sys.exit(1)

print(f"Found closing bracket at line {closing_idx}")

# New feeds to insert (with proper indentation)
new_feeds = [
            "# International Organizations & Standards",
            ("https://www.europol.europa.eu/rss", "europol", "Europol News"),
            ("https://www.fsb.org/rss", "fsb", "Financial Stability Board"),
            ("https://www.bankofengland.co.uk/rss/news", "boe", "Bank of England"),
            ("https://www.ietf.org/rfc/rfc-index.xml", "ietf", "IETF RFCs"),
            ("https://www.w3.org/News/news.rss", "w3c", "W3C News"),
]

# Insert before closing bracket
insertion_lines = []
for item in new_feeds:
    if isinstance(item, tuple):
        url, sid, name = item
        insertion_lines.append(f'            ("{url}", "{sid}", "{name}"),\n')
    else:
        # comment line
        insertion_lines.append(f'            {item}\n')

# Insert lines before closing bracket
lines[closing_idx:closing_idx] = insertion_lines

# Write back
with open('monitor_international.py', 'w') as f:
    f.writelines(lines)

print("Successfully added new feeds")
