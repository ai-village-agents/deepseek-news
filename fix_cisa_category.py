import re

with open('significance_filter.py', 'r') as f:
    content = f.read()

# Find detect_category function
pattern = r'(def detect_category\(item: Dict\) -> str:.*?)(?=\n\ndef|\nclass|\Z)'
match = re.search(pattern, content, re.DOTALL)
if match:
    func = match.group(1)
    # Insert CISA detection before geopolitical_tokens
    # We'll add after defense_tokens check, before geopolitical_tokens
    # Find the line with "if any(token in combined for token in geopolitical_tokens):"
    # Insert before that
    lines = func.split('\n')
    new_lines = []
    for i, line in enumerate(lines):
        new_lines.append(line)
        if 'if any(token in combined for token in geopolitical_tokens):' in line:
            # Insert CISA detection before this line
            new_lines.insert(i, '    if any(token in combined for token in ["cisa", "kev", "known exploited", "cybersecurity"]):')
            new_lines.insert(i+1, '        return "cisa"')
            new_lines.insert(i+2, '')
            break
    
    new_func = '\n'.join(new_lines)
    new_content = content.replace(func, new_func)
    
    with open('significance_filter.py', 'w') as f:
        f.write(new_content)
    print("Updated detect_category function")
else:
    print("Could not find detect_category function")
