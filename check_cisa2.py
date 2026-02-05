import json
with open('data_international/monitor_state.json') as f:
    data = json.load(f)
seen = data.get('seen_items', {})
cisa_items = [(k, v) for k, v in seen.items() if v.get('source_id') == 'cisa_kev']
print(f"Found {len(cisa_items)} CISA KEV items")
for key, val in cisa_items[:10]:
    print(f"{key[:50]}... | title: {val.get('title','')[:60]}... | processed: {val.get('processed', 'N')} | published: {val.get('published', 'N')}")
