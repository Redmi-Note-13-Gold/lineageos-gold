#!/usr/bin/env python3
"""storage-status.py <region> <sizes> <storage.txt> <ccache.txt>: a Markdown table of what the build
bucket holds and what this run did with it.

<sizes> has a line "<path> <bytes> <objects>" per top-level part of the bucket (repo-cache/<name>/,
ccache-files/, runs/); <storage.txt> is what the VM wrote about the source cache and the sync, and
<ccache.txt> is `ccache -s` after the build. Either of the last two may be missing. The monthly cost
is priced from Google's public price list (Cloud Billing Catalog API, Cloud Storage), with an access
token in $TOKEN."""
import json, os, re, sys, urllib.request

region, sizes_path, storage_path, ccache_path = sys.argv[1:5]

def read(path):
    try:
        with open(path) as f:
            return f.read()
    except OSError:
        return ''

info = dict(l.split('=', 1) for l in read(storage_path).splitlines() if '=' in l)
ccache = read(ccache_path)
sizes = []
for line in read(sizes_path).splitlines():
    path, size, objects = line.split()
    sizes.append((path, int(size), int(objects)))

def gb(n):
    return f'{n / 1e9:.1f} GB'

def short(rev):
    return f'`{rev[:12]}`' if rev else '?'

def price():
    try:
        url = 'https://cloudbilling.googleapis.com/v1/services/95FF-2EF5-5EA1/skus?pageSize=5000&currencyCode=USD'
        req = urllib.request.Request(url, headers={'Authorization': 'Bearer ' + os.environ['TOKEN']})
        for s in json.load(urllib.request.urlopen(req, timeout=60)).get('skus', []):
            if region in s.get('serviceRegions', []) and s['description'].startswith('Standard Storage'):
                rate = s['pricingInfo'][0]['pricingExpression']['tieredRates'][-1]['unitPrice']
                return int(rate.get('units', '0')) + rate.get('nanos', 0) / 1e9  # per GiB and month
    except Exception:
        pass
    return None

rows = []
for path, size, objects in sizes:
    if path.startswith('repo-cache/'):
        name = path.split('/')[1]
        held = f'security patch {name}'
        if info.get('cache') == name:
            held += f', vendor/lineage {short(info.get("cache_vendor_lineage"))} of {info.get("cache_commit_date", "?")}'
            held += f', made {info.get("cache_made", "?")}'
            run = (f'restored; synced to security patch {info.get("synced_patch", "?")}, vendor/lineage '
                   f'{short(info.get("synced_vendor_lineage"))} of {info.get("synced_commit_date", "?")}, '
                   f'{gb(int(info.get("fetched_bytes", 0)))} fetched on top')
        else:
            run = 'not used'
        rows.append((f'Source cache `{path}`', size, held, run))
    elif path.startswith('ccache-files/'):
        held = f'{objects} files, up to 50 GB'
        run = []
        if 'ccache_restored_bytes' in info:
            run.append(f'restored {gb(int(info["ccache_restored_bytes"]))}')
        m = re.search(r'^\s*Hits:\s+(\d+)\s*/\s*(\d+)', ccache, re.M)
        if m:
            hits, calls = int(m.group(1)), int(m.group(2))
            run.append(f'hit {hits} of {calls} ({100 * hits / calls:.1f}%)' if calls else 'no compiles')
        m = re.search(r'Cache size \(GB\):\s+([\d.]+)', ccache)
        if m:
            run.append(f'{m.group(1)} GB after the build')
        rows.append(('ccache `ccache-files/`', size, held, ', '.join(run) or 'not used'))
    elif path.startswith('runs/'):
        rows.append(('Logs and files `runs/`', size, f'{objects} files, each kept 30 days', ''))

print('| | Size | In the bucket | This run |')
print('| --- | ---: | --- | --- |')
for name, size, held, run in rows:
    print(f'| {name} | {gb(size)} | {held} | {run} |')
total = sum(size for _, size, _ in sizes)
rate = price()
month = f'about ${total / 2**30 * rate:.2f} a month' if rate else 'price unknown'
print(f'| **Total** | **{gb(total)}** | {month} | |')
