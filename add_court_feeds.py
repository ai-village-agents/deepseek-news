with open('monitor_international.py', 'r') as f:
    lines = f.readlines()

# Find the line with the closing bracket of feeds list
closing_idx = -1
for i, line in enumerate(lines):
    if line.rstrip() == '        ]' and i > 100:  # after line 100
        closing_idx = i
        break

if closing_idx == -1:
    print("Error: Could not find closing bracket")
    import sys
    sys.exit(1)

print(f"Found closing bracket at line {closing_idx}")

# New feeds to insert
new_feeds = [
            "# International Courts & Tribunals",
            ("https://pca-cpa.org/rss", "pca", "Permanent Court of Arbitration"),
            ("https://www.wto.org/rss", "wto", "World Trade Organization"),
]

# Insert before closing bracket
insertion_lines = []
for item in new_feeds:
    if isinstance(item, tuple):
        url, sid, name = item
        insertion_lines.append(f'            ("{url}", "{sid}", "{name}"),\n')
    else:
        insertion_lines.append(f'            {item}\n')

lines[closing_idx:closing_idx] = insertion_lines

with open('monitor_international.py', 'w') as f:
    f.writelines(lines)

print("Added court feeds")
