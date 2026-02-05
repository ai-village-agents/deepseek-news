import re

with open('batch_sec_historical_offset.py', 'r') as f:
    content = f.read()

# Add start_index and end_index to arguments
argparse_section = '''    parser.add_argument(
        "--start-index",
        type=int,
        default=0,
        help="Starting index in company list (default 0).",
    )
    parser.add_argument(
        "--end-index",
        type=int,
        default=None,
        help="Ending index in company list (default None = process all).",
    )'''

# Insert after company-limit argument
content = content.replace(
    '    parser.add_argument(\n        \"--company-limit\",\n        type=int,\n        default=100,\n        help=\"Number of companies to process (default 100).\",\n    )',
    '''    parser.add_argument(
        "--company-limit",
        type=int,
        default=100,
        help="Number of companies to process (default 100).",
    )
    parser.add_argument(
        "--start-index",
        type=int,
        default=0,
        help="Starting index in company list (default 0).",
    )
    parser.add_argument(
        "--end-index",
        type=int,
        default=None,
        help="Ending index in company list (default None = process all).",
    )'''
)

# Modify the line where selected_companies is defined
# Look for: selected_companies = companies[:self.company_limit]
content = content.replace(
    '        # Limit companies\n        selected_companies = companies[:self.company_limit]',
    '''        # Limit companies
        if self.end_index is None:
            self.end_index = self.start_index + self.company_limit
        selected_companies = companies[self.start_index:self.end_index]'''
)

# Update the class __init__ to accept start_index and end_index
# Find class definition line
class_start = content.find('class SECHistoricalBatchMiner:')
if class_start != -1:
    init_start = content.find('def __init__', class_start)
    if init_start != -1:
        # Find the __init__ parameters line
        init_line = content.find('(', init_start)
        init_end = content.find(')', init_line) + 1
        init_sig = content[init_start:init_end]
        # Add parameters
        new_sig = init_sig.replace(
            'self,',
            '''self,
        start_index: int = 0,
        end_index: Optional[int] = None,'''
        )
        content = content[:init_start] + new_sig + content[init_end:]

# Also need to add self.start_index and self.end_index assignments
# Find the __init__ body where assignments happen
init_body_start = content.find('def __init__', class_start)
if init_body_start != -1:
    # Find the first line after def __init__...:
    colon_pos = content.find(':', init_body_start)
    newline_after_colon = content.find('\n', colon_pos) + 1
    # Insert assignments after the first line
    indent = ' ' * 8
    assignments = f'\n{indent}self.start_index = start_index\n{indent}self.end_index = end_index'
    content = content[:newline_after_colon] + assignments + content[newline_after_colon:]

# Update the instantiation in main()
# Find: miner = SECHistoricalBatchMiner(
instantiate_start = content.find('    miner = SECHistoricalBatchMiner(')
if instantiate_start != -1:
    instantiate_end = content.find('\n        )', instantiate_start)
    if instantiate_end == -1:
        instantiate_end = content.find(')', instantiate_start) + 1
    instantiate_line = content[instantiate_start:instantiate_end]
    # Add start_index and end_index args
    new_instantiate = instantiate_line.replace(
        '        threshold=args.threshold,',
        '''        threshold=args.threshold,
        start_index=args.start_index,
        end_index=args.end_index,'''
    )
    content = content[:instantiate_start] + new_instantiate + content[instantiate_end:]

# Add Optional import if not present
if 'from typing import' in content:
    content = content.replace('from typing import', 'from typing import Optional,')
else:
    # Add at top after imports
    import_match = re.search(r'^import', content, re.MULTILINE)
    if import_match:
        pos = import_match.start()
        content = content[:pos] + 'from typing import Optional\n' + content[pos:]

with open('batch_sec_historical_offset.py', 'w') as f:
    f.write(content)

print("Modified batch_sec_historical_offset.py")
