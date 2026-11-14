"""Map the PAL recompiler seeds (seeds_main.txt) to another release through region_map's JSON.

usage: region_seeds.py <map.json> <pal function map> <pal seeds> <out seeds>
"""
import bisect
import json
import sys

m = json.load(open(sys.argv[1]))
fmap = {int(k, 16): int(v, 16) for k, v in m['functions'].items()}
sizes = sorted((int(l.split()[0], 16), int(l.split()[1]) * 4) for l in open(sys.argv[2]) if l.strip())
starts = [a for a, n in sizes]
out, miss = [], []
for line in open(sys.argv[3]):
    t = line.split('#')[0].strip()
    if not t:
        continue
    a = int(t, 16)
    i = bisect.bisect_right(starts, a) - 1
    f, n = sizes[i]
    if f in fmap and a < f + n:
        out.append('%08x' % (fmap[f] + a - f))
    else:
        miss.append(t)
open(sys.argv[4], 'w').write(chr(10).join(out) + chr(10))
print('seeds mapped %d, not mapped: %s' % (len(out), ' '.join(miss) or 'none'))
