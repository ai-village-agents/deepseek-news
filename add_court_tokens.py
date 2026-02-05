import re

with open('significance_filter.py', 'r') as f:
    lines = f.readlines()

gov_line = -1
for i, line in enumerate(lines):
    if 'if any(token in combined for token in ["fda", "noaa", "gov", "government", "who", "europol", "bank of england", "boe"]):' in line:
        gov_line = i
        break

if gov_line != -1:
    # Add court tokens
    line = lines[gov_line]
    # Insert before closing bracket
    new_line = line.replace('"boe"]', '"boe", "pca", "wto", "icj", "icc", "echr", "ohchr", "itlos"]')
    lines[gov_line] = new_line
    print("Updated government tokens with court tokens")

with open('significance_filter.py', 'w') as f:
    f.writelines(lines)

print("Done")
