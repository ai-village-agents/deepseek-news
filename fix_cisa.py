import sys

with open('monitor_international.py', 'r') as f:
    lines = f.readlines()

new_lines = []
i = 0
while i < len(lines):
    line = lines[i]
    new_lines.append(line)
    # Look for the recency check block
    if line.strip() == '# Check if recent' and i+2 < len(lines) and lines[i+1].strip() == 'if not self.is_recent(published_time):' and lines[i+2].strip() == 'continue':
        # Insert before this block
        # We need to go back and insert after the published_time assignment
        # Actually we need to modify the condition to skip for cisa_kev
        # Let's replace the continue line with a conditional
        new_lines.pop()  # remove the '# Check if recent' line we just added
        # Keep the comment line
        new_lines.append(line)  # re-add comment line
        # Add condition
        new_lines.append('                    # Skip recency check for CISA KEV\n')
        new_lines.append('                    if source_id != "cisa_kev" and not self.is_recent(published_time):\n')
        new_lines.append('                        continue\n')
        i += 3  # skip original three lines
        continue
    i += 1

with open('monitor_international.py', 'w') as f:
    f.writelines(new_lines)
print('Modified monitor_international.py')
