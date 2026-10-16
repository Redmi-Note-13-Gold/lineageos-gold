#!/usr/bin/env python3
"""build-times.py <.ninja_log or .ninja_log.gz>: a Markdown table of where the build's time went,
summed per kind of step. The times add up how long each step ran, so steps running side by side all
count, and a busy machine makes every step longer: they are not CPU time."""
import collections, gzip, re, sys

path = sys.argv[1]
opener = gzip.open if path.endswith('.gz') else open
steps = {}
with opener(path, 'rt', errors='replace') as f:
    for line in f:
        if line.startswith('#'):
            continue
        p = line.rstrip('\n').split('\t')
        if len(p) < 4:
            continue
        try:
            steps[p[3]] = (int(p[0]), int(p[1]))  # the last run of an output counts
        except ValueError:
            pass

def kind(o):
    if o.endswith(('.o', '.obj')): return 'C/C++ compile'
    if re.search(r'\.(so|a)$', o): return 'C/C++ link'
    if '/kotlin/' in o or o.endswith('.kt.jar'): return 'Kotlin compile'
    if '/javac/' in o or '/turbine' in o: return 'Java compile'
    if '/dex/' in o or '.dex' in o: return 'Dex (D8/R8)'
    if o.endswith(('.rlib', '.rmeta')) or '/rust/' in o: return 'Rust'
    if 'metalava' in o or 'stubs' in o: return 'API stubs (metalava)'
    if 'aapt' in o or '/res/' in o or o.endswith('.flata'): return 'Resources (aapt2)'
    if o.endswith(('.apk', '.apex', '.capex', '.img', '.zip')): return 'Packaging'
    if 'gen/' in o or '.srcjar' in o or 'aidl' in o: return 'Code generation'
    return 'Other'

total = collections.Counter(); count = collections.Counter()
for out, (s, e) in steps.items():
    k = kind(out); total[k] += max(0, e - s); count[k] += 1
all_ms = sum(total.values()) or 1
wall = (max(e for s, e in steps.values()) - min(s for s, e in steps.values())) / 1000 if steps else 0
print(f'{len(steps)} steps, {all_ms / 3.6e6:.1f} h of steps over {wall / 3600:.2f} h\n')
print('| Share | Step hours | Steps | Kind |')
print('| ---: | ---: | ---: | --- |')
for k, ms in total.most_common():
    print(f'| {100 * ms / all_ms:.1f}% | {ms / 3.6e6:.2f} | {count[k]} | {k} |')
