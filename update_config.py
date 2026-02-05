import re

with open("major_news_config.py", "r") as f:
    content = f.read()

# Find the weights section and add federal_register
# Look for pattern: "weights": { ... }
lines = content.split('\n')
in_weights = False
weight_bracket_count = 0
result_lines = []
added = False

for line in lines:
    if '"weights": {' in line:
        in_weights = True
        weight_bracket_count = 1
        result_lines.append(line)
    elif in_weights:
        if '{' in line:
            weight_bracket_count += line.count('{')
        if '}' in line:
            weight_bracket_count -= line.count('}')
        
        # Insert before the closing brace of weights
        if weight_bracket_count == 0 and not added:
            # Insert federal_register before this line
            indent = len(line) - len(line.lstrip())
            result_lines.append(f'{" " * indent}        "federal_register": 7.0,')
            added = True
        result_lines.append(line)
    else:
        result_lines.append(line)

if added:
    with open("major_news_config.py", "w") as f:
        f.write('\n'.join(result_lines))
    print("Added federal_register: 7.0 to MAJOR_NEWS_CONFIG weights")
else:
    print("Could not find weights section to update")
