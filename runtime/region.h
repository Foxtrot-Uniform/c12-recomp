// The release the build runs (PAL SCES-03364 or USA SCUS-94666). The runtime and the mods name game
// functions and data by their PAL addresses; GA() turns one into this build's address (identity in a PAL
// build). RAM offsets (without 0x80000000) are accepted too and come back as offsets.
#pragma once
#include <stdint.h>
#ifdef C12_USA
uint32_t region_addr(uint32_t pal);
#define GA(a) region_addr((uint32_t)(a))
#define C12_REGION_NAME "USA"
#define C12_NTSC 1
#else
#define GA(a) ((uint32_t)(a))
#define C12_REGION_NAME "PAL"
#define C12_NTSC 0
#endif
