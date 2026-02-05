import os
import re as regex

def fix_check_mainstream_coverage(filepath):
    with open(filepath, 'r') as f:
        content = f.read()
    
    # Check if already uses regex with word boundaries
    if 're.search' in content and r'\b' in content and 're.escape' in content:
        print(f"{filepath}: Already uses regex word boundaries")
        return False
    
    # Check if import re is present
    needs_import = 'import re' not in content and 'import re as' not in content
    
    lines = content.split('\n')
    modified = False
    
    for i, line in enumerate(lines):
        if 'def check_mainstream_coverage' in line:
            # Find the mainstream_keywords list
            for j in range(i, len(lines)):
                if 'mainstream_keywords' in lines[j] or 'mainstream_outlets' in lines[j]:
                    # Find the return statement
                    for k in range(j, len(lines)):
                        if 'return any(' in lines[k] or 'for keyword in' in lines[k] and 'if keyword.lower()' in lines.get(k+1, ''):
                            # This is the pattern to replace
                            indent = ' ' * (len(lines[k]) - len(lines[k].lstrip()))
                            
                            # Find haystack variable
                            haystack_line = -1
                            for l in range(i, k):
                                if 'haystack = ' in lines[l] or 'combined_text = ' in lines[l] or 'combined_raw = ' in lines[l]:
                                    haystack_line = l
                                    break
                            
                            if haystack_line == -1:
                                # Try to find variable name
                                for l in range(i, k):
                                    if '.lower()' in lines[l]:
                                        haystack_var = lines[l].split('=')[0].strip()
                                        break
                                else:
                                    haystack_var = 'haystack'
                            else:
                                haystack_var = lines[haystack_line].split('=')[0].strip()
                            
                            # Replace with proper regex loop
                            # We need to insert proper loop structure
                            # First, find where the function ends
                            end_idx = k
                            while end_idx < len(lines) and not (lines[end_idx].strip() == '' and lines[end_idx+1].strip().startswith('def ')):
                                end_idx += 1
                            
                            # Build replacement
                            replacement_lines = [
                                f"{indent}for keyword in mainstream_keywords:",
                                f"{indent}    pattern = r'\\b' + regex.escape(keyword.lower()) + r'\\b'",
                                f"{indent}    if regex.search(pattern, {haystack_var}):",
                                f"{indent}        return True",
                                f"{indent}return False"
                            ]
                            
                            # Remove old lines
                            lines_to_remove = []
                            for l in range(k, min(k+5, len(lines))):
                                if 'return' in lines[l] or lines[l].strip() == '':
                                    lines_to_remove.append(l)
                                else:
                                    break
                            
                            # Remove in reverse order
                            for l in sorted(lines_to_remove, reverse=True):
                                del lines[l]
                            
                            # Insert new lines at position k
                            for offset, new_line in enumerate(replacement_lines):
                                lines.insert(k + offset, new_line)
                            
                            modified = True
                            break
                    break
    
    if modified:
        # Add import re if needed
        if needs_import:
            # Find first import line
            import_idx = 0
            for idx, line in enumerate(lines):
                if line.startswith('import ') or line.startswith('from '):
                    import_idx = idx
                elif line.strip() and not line.startswith('#') and import_idx > 0:
                    # Insert after last import
                    lines.insert(import_idx + 1, 'import re')
                    break
            else:
                # Insert at top
                lines.insert(0, 'import re')
        
        # Write backup
        backup_path = filepath + '.backup.fixed'
        with open(backup_path, 'w') as f:
            f.write(content)
        
        # Write fixed file
        with open(filepath, 'w') as f:
            f.write('\n'.join(lines))
        
        print(f"Fixed {filepath} (backup: {backup_path})")
        return True
    
    print(f"No changes needed for {filepath}")
    return False

# Fix all files
files_to_fix = [
    'monitor.py',
    'monitor_enhanced.py',
    'major_news_monitor.py',
    'monitor_international_enhanced.py',
    'monitor_international_enhanced_v2.py',
    'monitor_international_enhanced_git.py'
]

for f in files_to_fix:
    if os.path.exists(f):
        fix_check_mainstream_coverage(f)
    else:
        print(f"File {f} not found")
