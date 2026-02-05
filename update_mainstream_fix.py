import re as regex_lib
import os

def update_file(filename):
    with open(filename, 'r') as f:
        content = f.read()
    
    # Check if file already uses regex pattern
    if 're.search' in content and 'r\'\\b\'' in content:
        print(f"Skipping {filename} - already uses regex")
        return False
    
    # Find function definition
    lines = content.split('\n')
    updated = False
    
    for i, line in enumerate(lines):
        if 'def check_mainstream_coverage' in line:
            # Find the start of function body
            j = i + 1
            while j < len(lines) and not lines[j].strip().startswith('"""'):
                j += 1
            # Skip docstring
            while j < len(lines) and lines[j].strip().startswith('"'):
                j += 1
            
            # Now look for the mainstream keyword loop
            for k in range(j, len(lines)):
                if any(keyword in lines[k] for keyword in ['mainstream_keywords', 'mainstream_outlets']):
                    # Find the loop
                    for l in range(k, len(lines)):
                        if 'for keyword in' in lines[l] or 'for outlet in' in lines[l]:
                            # Find the condition line
                            for m in range(l, len(lines)):
                                if 'keyword.lower() in combined_text' in lines[m] or 'outlet.lower() in combined_text' in lines[m] or 'keyword.lower() in haystack' in lines[m]:
                                    # Replace this line with regex pattern
                                    old_line = lines[m]
                                    if 'combined_text' in old_line:
                                        var_name = 'combined_text'
                                    elif 'haystack' in old_line:
                                        var_name = 'haystack'
                                    else:
                                        var_name = 'haystack'
                                    
                                    # Build regex replacement
                                    indent = ' ' * (len(old_line) - len(old_line.lstrip()))
                                    lines[m] = f'{indent}pattern = r\'\\b\' + regex_lib.escape(keyword.lower()) + r\'\\b\''
                                    lines.insert(m+1, f'{indent}match = regex_lib.search(pattern, {var_name})')
                                    lines.insert(m+2, f'{indent}if match:')
                                    
                                    # Update the next line which is the if body
                                    # Find the line after that
                                    for n in range(m+3, len(lines)):
                                        if lines[n].strip() and not lines[n].strip().startswith('#'):
                                            # This is the if body, keep it
                                            # Need to adjust indentation
                                            body_indent = ' ' * (len(lines[n]) - len(lines[n].lstrip()))
                                            lines[n] = body_indent + lines[n].lstrip()
                                            break
                                    
                                    updated = True
                                    break
                            break
                    break
    
    if updated:
        # Ensure import re is present
        if 'import re' not in content and 'import re as' not in content:
            # Add import at top after other imports
            for idx, line in enumerate(lines):
                if line.startswith('import ') or line.startswith('from '):
                    continue
                else:
                    lines.insert(idx, 'import re')
                    break
        
        new_content = '\n'.join(lines)
        # Backup original
        backup = filename + '.backup.mainstream_fix'
        with open(backup, 'w') as f:
            f.write(content)
        
        with open(filename, 'w') as f:
            f.write(new_content)
        print(f"Updated {filename} (backup: {backup})")
        return True
    else:
        print(f"No changes needed for {filename}")
        return False

# Update all relevant files
files = [
    'monitor.py',
    'monitor_enhanced.py', 
    'major_news_monitor.py',
    'monitor_international_enhanced.py',
    'monitor_international_enhanced_v2.py',
    'monitor_international_enhanced_git.py'
]

for f in files:
    if os.path.exists(f):
        update_file(f)
    else:
        print(f"File {f} not found")
