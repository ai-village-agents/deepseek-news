import sys

with open('significance_filter.py.tmp', 'r') as f:
    lines = f.readlines()

# Find the weights dict
weights_start = None
weights_end = None
in_weights = False
for i, line in enumerate(lines):
    if '"weights": {' in line:
        weights_start = i
        in_weights = True
        continue
    if in_weights and line.strip() == '},':
        weights_end = i
        break

if weights_start is None or weights_end is None:
    print("Weights dict not found")
    sys.exit(1)

# Insert after nasdaq_halt line
insert_line = None
for i in range(weights_start, weights_end):
    if '"nasdaq_halt":' in lines[i]:
        insert_line = i + 1
        # Ensure we maintain proper indentation
        indent = len(lines[i]) - len(lines[i].lstrip())
        break

if insert_line is None:
    # fallback: insert before the closing brace
    insert_line = weights_end

indent = ' ' * 8  # 8 spaces (two tabs) based on the file style
cisa_line = f'{indent}"cisa": 7.0,\n'

lines.insert(insert_line, cisa_line)

with open('significance_filter.py.tmp', 'w') as f:
    f.writelines(lines)

print(f"Added cisa weight at line {insert_line}")
