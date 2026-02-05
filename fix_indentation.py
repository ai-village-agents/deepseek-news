import re

with open('significance_filter.py', 'r') as f:
    lines = f.readlines()

# Find the problematic section
for i, line in enumerate(lines):
    if 'if any(token in combined for token in ["cisa", "kev", "known exploited", "cybersecurity"]):' in line:
        # Check if next line is properly indented
        if i+1 < len(lines) and lines[i+1].strip() == 'return "cisa"':
            # Check if line after return has proper indentation
            if i+2 < len(lines) and not lines[i+2].startswith('    '):
                lines[i+2] = '    ' + lines[i+2]
        break

with open('significance_filter.py', 'w') as f:
    f.writelines(lines)
print("Fixed indentation")
