"""Map addresses of the European executable (SCES-03364) to another release of the same game.

usage: region_map.py <pal exe> <pal function map> <other exe> <out.json> [<out C table>]

Both executables are the same program with small edits, so most functions are identical apart from
absolute addresses (jal targets, lui/addiu pairs, gp-relative globals). A function is matched when its
instructions with those fields masked occur exactly once in the other executable. Data addresses are
paired from matched functions: the same instruction forms an absolute address (lui + imm, or gp + imm)
in both. Output: {"functions": {pal: other}, "data": [[pal, other], ...], "gp": [pal, other]}.
"""
import bisect
import json
import struct
import sys


def load(path):
    b = open(path, 'rb').read()
    pc, gp, taddr, tsize = struct.unpack_from('<IIII', b, 0x10)
    words = list(struct.unpack('<%dI' % (tsize // 4), b[0x800:0x800 + tsize]))
    return words, taddr, pc


def norm(x):
    op = x >> 26
    if op == 0:                    # SPECIAL: keep everything (registers, shift amounts)
        return x
    if op in (2, 3):               # j / jal: target differs
        return op << 26
    if op in (1, 4, 5, 6, 7, 20, 21, 22, 23):   # branches: offsets are internal, keep
        return x
    if op == 0x0f:                 # lui: immediate differs
        return x & 0xffff0000
    if op in (0x08, 0x09, 0x0a, 0x0b, 0x0c, 0x0d, 0x0e) or (0x20 <= op <= 0x2e) or op in (0x32, 0x3a):
        return x & 0xffff0000      # immediates / offsets may be addresses
    return x


def gp_of(words, base, pc):
    # the start code sets gp with lui gp, hi / addiu gp, gp, lo
    i = (pc - base) // 4
    hi = None
    for k in range(i, min(i + 64, len(words))):
        w = words[k]
        if w >> 16 == 0x3c1c:
            hi = (w & 0xffff) << 16
        elif hi is not None and (w >> 16) in (0x279c, 0x379c):
            lo = w & 0xffff
            return (hi + (lo - 0x10000 if (w >> 16) == 0x279c and lo >= 0x8000 else lo)) & 0xffffffff
    return None


def addresses(words, start, n, gp):
    """absolute addresses formed by each instruction of a function (index -> address)"""
    out = {}
    hi = {}
    for k in range(n):
        w = words[start + k]
        op, rs, rt, imm = w >> 26, (w >> 21) & 31, (w >> 16) & 31, w & 0xffff
        simm = imm - 0x10000 if imm >= 0x8000 else imm
        if op == 0x0f:
            hi[rt] = imm << 16
            continue
        if op in (0x09, 0x0d) or (0x20 <= op <= 0x2e) or op in (0x32, 0x3a):
            if rs == 28 and gp is not None:
                out[k] = (gp + simm) & 0xffffffff
            elif rs in hi:
                out[k] = (hi[rs] + (imm if op == 0x0d else simm)) & 0xffffffff
            if op in (0x09, 0x0d) and rt != rs:
                hi.pop(rt, None)
        elif op == 0 and (w & 0x3f) in (0x21, 0x25) and ((w >> 11) & 31) in hi:
            hi.pop((w >> 11) & 31, None)
    return out


def main():
    pal, pbase, ppc = load(sys.argv[1])
    oth, obase, opc = load(sys.argv[3])
    funcs = []
    for line in open(sys.argv[2]):
        p = line.split()
        if len(p) >= 2:
            funcs.append((int(p[0], 16), int(p[1])))
    pn = [norm(x) for x in pal]
    on = [norm(x) for x in oth]
    K = 6
    index = {}
    for i in range(len(on) - K):
        index.setdefault(tuple(on[i:i + K]), []).append(i)
    fmap = {}
    for addr, size in funcs:
        s = (addr - pbase) // 4
        if size < 3 or s + size > len(pn):
            continue
        key = tuple(pn[s:s + min(K, size)])
        cands = [c for c in index.get(key, []) if on[c:c + size] == pn[s:s + size]]
        if len(cands) == 1:
            fmap[addr] = obase + cands[0] * 4
    # functions that differ (edited for the other release): their first instructions, if found once
    for addr, size in funcs:
        if addr in fmap or size < 8:
            continue
        s = (addr - pbase) // 4
        key = pn[s:s + 8]
        cands = [c for c in index.get(tuple(key[:K]), []) if on[c:c + 8] == key]
        if len(cands) == 1:
            fmap[addr] = obase + cands[0] * 4
    # the rest: placed between matched neighbours with the same shift
    matched = sorted(fmap)
    for addr, size in funcs:
        if addr in fmap:
            continue
        i = bisect.bisect_left(matched, addr)
        if 0 < i < len(matched):
            a, b = matched[i - 1], matched[i]
            if fmap[a] - a == fmap[b] - b:
                fmap[addr] = addr + fmap[a] - a
    pgp, ogp = gp_of(pal, pbase, ppc), gp_of(oth, obase, opc)
    pairs = {}
    conflicts = 0
    for addr, size in funcs:
        if addr not in fmap:
            continue
        s, t = (addr - pbase) // 4, (fmap[addr] - obase) // 4
        if pn[s:s + size] != on[t:t + size]:
            continue
        pa, oa = addresses(pal, s, size, pgp), addresses(oth, t, size, ogp)
        for k, v in pa.items():
            if k in oa and 0x80000000 <= v < 0x80200000:
                if v in pairs and pairs[v] != oa[k]:
                    conflicts += 1
                pairs.setdefault(v, oa[k])
    data = sorted(pairs.items())
    json.dump({"functions": {'%08x' % k: '%08x' % v for k, v in sorted(fmap.items())},
               "data": [['%08x' % a, '%08x' % b] for a, b in data],
               "gp": ['%08x' % (pgp or 0), '%08x' % (ogp or 0)],
               "entry": ['%08x' % ppc, '%08x' % opc]},
              open(sys.argv[4], 'w'), indent=0)
    if len(sys.argv) > 5:   # a C table for the runtime: functions (start, size) and data pairs
        same = set(a for a, n in funcs if a in fmap and pn[(a - pbase) // 4:(a - pbase) // 4 + n] ==
                   on[(fmap[a] - obase) // 4:(fmap[a] - obase) // 4 + n])
        lines = ['// generated by tools/region_map.py: PAL (SCES-03364) -> this release',
                 'static const RegionFn k_region_fn[] = {']
        for a, n in funcs:
            if a in fmap:
                lines.append('    {0x%08xu, 0x%08xu, %d, %d},' % (a, fmap[a], n * 4, 1 if a in same else 0))
        lines.append('};')
        lines.append('static const RegionData k_region_data[] = {')
        for a, v in data:
            lines.append('    {0x%08xu, 0x%08xu},' % (a, v))
        lines.append('};')
        lines.append('static const u32 k_region_gp[2] = {0x%08xu, 0x%08xu};' % (pgp or 0, ogp or 0))
        with open(sys.argv[5], 'w') as f:
            f.write(chr(10).join(lines) + chr(10))
    exact = sum(1 for a, s in funcs if a in fmap)
    print('functions mapped %d of %d, data pairs %d (conflicts %d), gp %08x -> %08x, entry %08x -> %08x'
          % (exact, len(funcs), len(data), conflicts, pgp or 0, ogp or 0, ppc, opc))


if __name__ == '__main__':
    main()
