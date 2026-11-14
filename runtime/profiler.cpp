// Sampling profiler for performance work: env C12_PROFILE=1 samples the main thread's instruction
// pointer every millisecond and, at exit, writes profile.txt: the functions it was found in most
// (symbols from the exe's PDB). Off unless asked for.
#define WIN32_LEAN_AND_MEAN
#define NOMINMAX
#include <windows.h>
#include <mmsystem.h>
#include <dbghelp.h>
#include <stdio.h>
#include <stdlib.h>
#include <atomic>
#include <thread>
#include <unordered_map>
#include <vector>
#include <algorithm>
#include <string>
#pragma comment(lib, "dbghelp.lib")

static HANDLE g_main;
static std::atomic<bool> g_run;
// samples go to a fixed buffer: the sampler must not allocate while the main thread is suspended (it may
// hold the heap lock)
static DWORD64 g_buf[1 << 21];
static unsigned g_total;
static std::thread g_th;

static void sampler() {
    timeBeginPeriod(1);
    while (g_run) {
        Sleep(1);
        if (SuspendThread(g_main) == (DWORD)-1) continue;
        CONTEXT ctx = {};
        ctx.ContextFlags = CONTEXT_CONTROL;
        if (GetThreadContext(g_main, &ctx) && g_total < (1u << 21)) g_buf[g_total++] = ctx.Rip;
        ResumeThread(g_main);
    }
}

void profiler_stop();
void profiler_start() {
    const char* e = getenv("C12_PROFILE");
    if (!e || !*e || *e == '0') return;
    DuplicateHandle(GetCurrentProcess(), GetCurrentThread(), GetCurrentProcess(), &g_main, 0, FALSE, DUPLICATE_SAME_ACCESS);
    g_run = true;
    g_th = std::thread(sampler);
    atexit(profiler_stop);
}

void profiler_stop() {
    if (!g_run) return;
    g_run = false;
    g_th.join();
    HANDLE proc = GetCurrentProcess();
    SymSetOptions(SYMOPT_UNDNAME | SYMOPT_DEFERRED_LOADS);
    SymInitialize(proc, nullptr, TRUE);
    std::unordered_map<std::string, unsigned> by_fn;
    std::unordered_map<DWORD64, unsigned> hits;
    for (unsigned i = 0; i < g_total; i++) hits[g_buf[i]]++;
    for (auto& h : hits) {
        char buf[sizeof(SYMBOL_INFO) + 256] = {};
        SYMBOL_INFO* s = (SYMBOL_INFO*)buf;
        s->SizeOfStruct = sizeof(SYMBOL_INFO);
        s->MaxNameLen = 255;
        DWORD64 disp = 0;
        std::string name;
        if (SymFromAddr(proc, h.first, &disp, s)) name = s->Name;
        else {
            char m[MAX_PATH] = "?";
            HMODULE mod = nullptr;
            if (GetModuleHandleExA(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS | GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT, (LPCSTR)h.first, &mod))
                GetModuleFileNameA(mod, m, MAX_PATH);
            name = std::string("[") + (strrchr(m, '\\') ? strrchr(m, '\\') + 1 : m) + "]";
        }
        by_fn[name] += h.second;
    }
    std::vector<std::pair<std::string, unsigned>> v(by_fn.begin(), by_fn.end());
    std::sort(v.begin(), v.end(), [](auto& a, auto& b) { return a.second > b.second; });
    FILE* f = fopen("profile.txt", "w");
    if (!f) return;
    fprintf(f, "%u samples (1 ms) of the main thread\n", g_total);
    for (size_t i = 0; i < v.size() && i < 60; i++) fprintf(f, "%6.2f%%  %s\n", 100.0 * v[i].second / std::max(1u, g_total), v[i].first.c_str());
    fclose(f);
}
