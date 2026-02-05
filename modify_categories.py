import re

with open('significance_filter.py', 'r') as f:
    lines = f.readlines()

# Find line numbers for token lists
gov_line = -1
reg_line = -1
for i, line in enumerate(lines):
    if 'if any(token in combined for token in ["fda", "noaa", "gov", "government"]):' in line:
        gov_line = i
    elif 'if any(token in combined for token in ["rfc", "ietf", "regulatory"]):' in line:
        reg_line = i

print(f"Government token line: {gov_line}")
print(f"Regulatory token line: {reg_line}")

if gov_line != -1:
    # Extract the line with tokens
    # The token list is on the same line
    line = lines[gov_line]
    # Add tokens before the closing bracket
    # Pattern: ["fda", "noaa", "gov", "government"]
    if '"government"' in line:
        # Replace with extended list
        new_line = line.replace('"government"', '"government", "who", "europol", "bank of england", "boe"')
        lines[gov_line] = new_line
        print("Updated government tokens")

if reg_line != -1:
    line = lines[reg_line]
    if '"ietf"' in line:
        new_line = line.replace('"ietf"', '"ietf", "w3c", "fsb"')
        lines[reg_line] = new_line
        print("Updated regulatory tokens")

# Write back
with open('significance_filter.py', 'w') as f:
    f.writelines(lines)

print("Categories updated")
