// PAL -> USA address translation for the runtime and mods (see region.h). The table comes from
// tools/region_map.py: functions matched between the two executables (start, size, identical code) and
// data addresses paired from the instructions of identical functions.
#include "psx.h"
#include "region.h"
#ifdef C12_USA
#include <algorithm>
#include <unordered_map>
struct RegionFn { u32 pal, usa, size, same; };
struct RegionData { u32 pal, usa; };
#include "region_usa.inc"

static u32 lookup(u32 a, bool& ok) {
    ok = true;
    if (a < 0x80010000u || a >= 0x80200000u) return a;   // BIOS area, the stack's top, not game data
    const size_t nf = sizeof k_region_fn / sizeof k_region_fn[0];
    const RegionFn* f = std::upper_bound(k_region_fn, k_region_fn + nf, a, [](u32 v, const RegionFn& e) { return v < e.pal; });
    if (f != k_region_fn) {
        --f;
        if (a < f->pal + f->size) {
            if (a != f->pal && !f->same) ok = false;   // inside a function that differs: the offset is a guess
            return f->usa + (a - f->pal);
        }
    }
    const size_t nd = sizeof k_region_data / sizeof k_region_data[0];
    const RegionData* d = std::upper_bound(k_region_data, k_region_data + nd, a, [](u32 v, const RegionData& e) { return v < e.pal; });
    const RegionData* lo = d != k_region_data ? d - 1 : nullptr;
    const RegionData* hi = d != k_region_data + nd ? d : nullptr;
    if (lo && lo->pal == a) return lo->usa;
    if (lo && hi && lo->usa - lo->pal == hi->usa - hi->pal) return a + (lo->usa - lo->pal);
    ok = false;
    if (lo && a - lo->pal < 0x400) return a + (lo->usa - lo->pal);
    if (hi) return a + (hi->usa - hi->pal);
    return a;
}

uint32_t region_addr(uint32_t pal) {
    static std::unordered_map<u32, u32> cache;
    auto it = cache.find(pal);
    if (it != cache.end()) return it->second;
    bool offset = pal < 0x00200000u;
    u32 a = offset ? (pal | 0x80000000u) : pal;
    bool ok;
    u32 r = lookup(a, ok);
    if (offset) r &= 0x1FFFFFu;
    if (!ok) logf("region: no exact US address for PAL %08x, using %08x\n", a, r | (offset ? 0x80000000u : 0));
    cache[pal] = r;
    return r;
}
#endif
