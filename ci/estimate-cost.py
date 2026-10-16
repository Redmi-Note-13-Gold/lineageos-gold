#!/usr/bin/env python3
"""estimate-cost.py <region> <machine type> <disk GB> <seconds> <egress GB>: estimate what a build VM cost,
from Google's public price list (Cloud Billing Catalog API, Compute Engine). Prints a Markdown table.
Needs an access token in $TOKEN. The exact figure shows up in the billing reports a day later, under the
VM's labels."""
import json, os, sys, urllib.request

region, machine, disk_gb, secs, egress_gb = sys.argv[1], sys.argv[2], float(sys.argv[3]), float(sys.argv[4]), float(sys.argv[5])
family, kind, cpus = machine.split('-')
cpus = int(cpus)
ram_gb = {'standard': 4, 'highcpu': 2, 'highmem': 8}[kind] * cpus
fam_desc = {'c2d': 'C2D AMD', 'n2d': 'N2D AMD', 'c3d': 'C3D', 'n2': 'N2 ', 'e2': 'E2 '}[family]

url = 'https://cloudbilling.googleapis.com/v1/services/6F81-5844-456A/skus?pageSize=5000&currencyCode=USD'
skus, token = [], ''
while True:
    req = urllib.request.Request(url + ('&pageToken=' + token if token else ''),
                                 headers={'Authorization': 'Bearer ' + os.environ['TOKEN']})
    page = json.load(urllib.request.urlopen(req, timeout=120))
    skus += page.get('skus', []); token = page.get('nextPageToken', '')
    if not token:
        break

def price(match):
    for s in skus:
        if region in s.get('serviceRegions', []) and match(s['description']):
            rate = s['pricingInfo'][0]['pricingExpression']['tieredRates'][-1]['unitPrice']
            return int(rate.get('units', '0')) + rate.get('nanos', 0) / 1e9
    return None

spot = 'Spot Preemptible ' + fam_desc
core = price(lambda d: d.startswith(spot) and 'Instance Core' in d and 'Custom' not in d)
ram = price(lambda d: d.startswith(spot) and 'Instance Ram' in d and 'Custom' not in d)
disk = price(lambda d: d.startswith('Balanced PD Capacity'))
egress = price(lambda d: 'Network Internet Egress' in d and 'Premium' in d) or 0.12
hours = secs / 3600
rows = [
    ('VM', f'{machine} spot, {hours:.2f} h', (core * cpus + ram * ram_gb) * hours if core and ram else None),
    ('Disk', f'{disk_gb:.0f} GB balanced PD, {hours:.2f} h', disk * disk_gb * hours / 730 if disk else None),
    ('Download of the files', f'{egress_gb:.2f} GB to the internet', egress * egress_gb),
]
total = sum(c for _, _, c in rows if c is not None)
print('| | | Estimate (USD) |')
print('| --- | --- | ---: |')
for name, what, cost in rows:
    print(f'| {name} | {what} | ' + (f'{cost:.3f}' if cost is not None else '?') + ' |')
print(f'| **Total** | | **{total:.3f}** |')
