import sys

with open('significance_filter.py.tmp', 'r') as f:
    lines = f.readlines()

# 1. Add "cisa" to apply_to_categories list
in_block = False
inserted = False
for i, line in enumerate(lines):
    if '"apply_to_categories": [' in line:
        in_block = True
    if in_block and line.strip() == '],':
        # Insert before closing bracket
        # Find the line with "arxiv", then insert after the empty line following it
        # Actually we need to find line with "arxiv", then insert after the empty line after that
        # Let's search backwards from i
        for j in range(i-1, 0, -1):
            if '"arxiv"' in lines[j]:
                # Insert at j+2 (skip the empty line after arxiv)
                # But we need to maintain pattern: category line, empty line
                # So we insert at j+1 (the empty line), replace with category line + empty line
                indent = ' ' * 12  # 12 spaces
                cisa_line = indent + '"cisa",\n'
                empty_line = '\n'
                # Insert after the empty line (j+1)
                lines.insert(j+2, cisa_line)
                lines.insert(j+3, empty_line)
                inserted = True
                print(f'Inserted "cisa" at line {j+2}')
                break
        break

if not inserted:
    print("Could not find arxiv in apply_to_categories")
    # Fallback: just append before closing bracket
    for i, line in enumerate(lines):
        if line.strip() == '],':
            indent = ' ' * 12
            lines.insert(i, indent + '"cisa",\n')
            lines.insert(i+1, '\n')
            print(f'Inserted "cisa" before closing bracket at line {i}')
            break

# 2. Ensure CISA detection is correct (already there)

# 3. Write to original file
with open('significance_filter.py', 'w') as f:
    f.writelines(lines)

print("Fixed significance_filter.py")
