import sys

with open('significance_filter.py', 'r') as f:
    lines = f.readlines()

# Find the line with "# CISA KEV detection"
for i, line in enumerate(lines):
    if '# CISA KEV detection' in line:
        # Insert new check before the token detection
        indent = '    ' * (line.count('    ') + 1)  # Keep same indentation level
        new_line = indent + '# Check source_id for CISA KEV\n'
        new_line += indent + 'if item.get("source_id") == "cisa_kev":\n'
        new_line += indent + '    return "cisa"\n'
        # Insert after the comment line
        lines.insert(i + 1, new_line)
        break

with open('significance_filter.py', 'w') as f:
    f.writelines(lines)

print("Added source_id check for CISA KEV detection")
