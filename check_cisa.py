import json
with open('data_international/monitor_state.json') as f:
    data = json.load(f)
count = 0
for key, val in data.items():
    if val.get('source_id') == 'cisa_kev':
        print(f"{key[:50]}... | title: {val.get('title','')[:60]}... | processed: {val.get('processed', 'N')} | published: {val.get('published', 'N')}")
        count += 1
        if count >= 10:
            break
print(f"Total cisa_kev entries: {sum(1 for v in data.values() if v.get('source_id') == 'cisa_kev')}")
