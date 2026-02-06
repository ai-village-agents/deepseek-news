import os
import re
import glob
import json
from datetime import datetime, timezone

def parse_md(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    if not content.startswith('---'):
        return None
    parts = content.split('---', 2)
    if len(parts) < 3:
        return None
    front = parts[1]
    data = {}
    for line in front.strip().split('\n'):
        if ': ' in line:
            k, v = line.split(': ', 1)
            data[k.strip()] = v.strip()
    try:
        data['significance'] = float(data.get('significance', 0))
    except:
        data['significance'] = 0
    # get source type from filename
    basename = os.path.basename(filepath)
    m = re.match(r'.*?-(\w+)-[a-f0-9]+\.md', basename)
    data['source_type'] = m.group(1) if m else 'unknown'
    # get file timestamp
    m2 = re.match(r'(\d{4})-(\d{2})-(\d{2})-(\d{2})-(\d{2})-(\d{2})', basename)
    if m2:
        y, mo, d, h, mi, s = map(int, m2.groups())
        data['file_dt'] = datetime(y, mo, d, h, mi, s, tzinfo=timezone.utc)
    else:
        data['file_dt'] = None
    data['title'] = data.get('title', '')
    data['url'] = data.get('source_url', '')
    data['filename'] = basename
    data['filepath'] = filepath
    return data

def assign_category(data):
    title = data['title'].lower()
    source = data['source_type']
    # categorize
    if source == 'sec_edgar_batch':
        if '8-k' in title.lower():
            return 'sec_8k_material_event'
        elif '10-k' in title.lower() or '10-q' in title.lower():
            return 'sec_earnings_filing'
        else:
            return 'sec_other_filing'
    elif source == 'prnewswire':
        if any(term in title for term in ['earnings', 'results', 'revenue', 'profit', 'quarter']):
            return 'corporate_earnings'
        elif any(term in title for term in ['raises', 'funding', 'investment', '$', 'million', 'billion']):
            return 'funding_round'
        elif any(term in title for term in ['merger', 'acquisition', 'acquires', 'buys']):
            return 'merger_acquisition'
        elif any(term in title for term in ['lawsuit', 'settlement', 'verdict', 'suit']):
            return 'legal_action'
        else:
            return 'corporate_announcement'
    elif source in ('us_navy', 'us_army', 'dod_news'):
        return 'defense_military'
    elif source == 'cisa_kev':
        return 'cybersecurity_vulnerability'
    elif source == 'federal_register':
        return 'government_regulation'
    elif source == 'nasa_breaking':
        return 'space_science'
    elif source == 'who_news':
        return 'health_who'
    else:
        return 'other'

def score_potential_spread(data, category):
    # heuristic for likely media coverage
    base = data['significance']
    # adjust based on category
    if category in ('sec_8k_material_event', 'corporate_earnings', 'merger_acquisition'):
        base *= 1.5  # high financial media interest
    elif category in ('defense_military', 'cybersecurity_vulnerability'):
        base *= 1.3  # specialized but important
    elif category in ('government_regulation', 'space_science'):
        base *= 1.2  # niche but can be big
    # check for major company names
    title = data['title'].lower()
    major_companies = ['mastercard', 'amazon', 'jpmorgan', 'oracle', 'illumina', 
                       'cleanspark', 'philip morris', 'alphabet', 'google']
    for comp in major_companies:
        if comp in title:
            base *= 1.4
            break
    return base

def main():
    posts = []
    for filepath in glob.glob('_posts/*2026-02-0[5-6]*.md'):
        data = parse_md(filepath)
        if data and data['significance'] >= 7.0:
            data['category'] = assign_category(data)
            data['spread_score'] = score_potential_spread(data, data['category'])
            posts.append(data)
    
    print(f"Analyzing {len(posts)} high-significance posts from Feb 5-6")
    
    # Sort by spread score
    posts.sort(key=lambda x: x['spread_score'], reverse=True)
    
    # Output top 20
    print("\n=== TOP 20 CANDIDATES BY SPREAD POTENTIAL ===")
    for i, p in enumerate(posts[:20]):
        print(f"{i+1:2d}. Spread: {p['spread_score']:.2f} | Sig: {p['significance']:.2f} | "
              f"Source: {p['source_type']:15s} | Cat: {p['category']:25s}")
        print(f"    Title: {p['title'][:80]}")
        print(f"    Date: {p['file_dt']}")
        print()
    
    # Group by category
    cats = {}
    for p in posts[:50]:
        cat = p['category']
        cats[cat] = cats.get(cat, 0) + 1
    
    print("\n=== CATEGORY DISTRIBUTION (top 50) ===")
    for cat, cnt in sorted(cats.items(), key=lambda x: x[1], reverse=True):
        print(f"{cat:30s}: {cnt:3d}")
    
    # Select top 5, trying to diversify categories
    selected = []
    seen_cats = set()
    for p in posts:
        if p['category'] not in seen_cats:
            selected.append(p)
            seen_cats.add(p['category'])
        if len(selected) >= 5:
            break
    
    # If not enough categories, fill with highest spread
    if len(selected) < 5:
        for p in posts:
            if p not in selected:
                selected.append(p)
            if len(selected) >= 5:
                break
    
    print("\n=== PROPOSED TOP 5 (DIVERSE CATEGORIES) ===")
    for i, p in enumerate(selected):
        print(f"\n{i+1}. {p['title']}")
        print(f"   Category: {p['category']}")
        print(f"   Source: {p['source_type']}")
        print(f"   Significance: {p['significance']:.2f}")
        print(f"   Spread Score: {p['spread_score']:.2f}")
        print(f"   Published: {p['file_dt']}")
        print(f"   URL: {p['url']}")
        print(f"   File: {p['filename']}")
    
    # Save selection for webpage generation
    with open('top5_selection.json', 'w') as f:
        json.dump([{k: v for k, v in p.items() if k != 'filepath'} for p in selected], f, indent=2, default=str)
    
    print("\nSaved to top5_selection.json")

if __name__ == '__main__':
    main()
