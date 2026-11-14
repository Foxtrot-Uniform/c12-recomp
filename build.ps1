# Regenerate recompiled C and build c12.exe (MSVC + Ninja). -Region USA: the US release (disc_usa\, gen_usa\,
# build_usa\, c12_usa.exe).
param([switch]$NoRecomp, [string]$Config = "RelWithDebInfo", [ValidateSet("PAL", "USA")][string]$Region = "PAL")
$ErrorActionPreference = "Stop"
$root = $PSScriptRoot
$vs = "C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools"
if (-not $env:VSCMD_VER) {
    cmd /c "`"$vs\VC\Auxiliary\Build\vcvars64.bat`" >nul 2>&1 && set" | ForEach-Object {
        if ($_ -match '^([^=]+)=(.*)$') { Set-Item -Path "env:$($matches[1])" -Value $matches[2] }
    }
}
$usa = $Region -eq "USA"
$bdir = if ($usa) { "$root\build_usa" } else { "$root\build" }
if (-not $NoRecomp) {
    if ($usa) {
        # PAL addresses -> US ones (the runtime's table and the recompiler's seeds)
        python "$root\tools\region_map.py" "$root\disc\SCES_033.64" "$root\gen\main_map.txt" "$root\disc_usa\SCUS_946.66" "$root\re\usa\map.json" "$root\runtime\region_usa.inc"
        python "$root\tools\region_seeds.py" "$root\re\usa\map.json" "$root\gen\main_map.txt" "$root\seeds_main.txt" "$root\seeds_main_usa.txt"
    }
    python "$root\tools\recomp\recomp.py" $(if ($usa) { "$root\recomp_usa.json" } else { "$root\recomp.json" }); if ($LASTEXITCODE) { exit 1 }
}
$cmake = "$vs\Common7\IDE\CommonExtensions\Microsoft\CMake\CMake\bin\cmake.exe"
if (-not (Test-Path "$bdir\build.ninja")) {
    & $cmake -S $root -B $bdir -G Ninja "-DCMAKE_BUILD_TYPE=$Config" -DCMAKE_C_COMPILER=cl -DCMAKE_CXX_COMPILER=cl "-DC12_REGION=$Region" | Out-Host
    if ($LASTEXITCODE) { exit 1 }
}
& $cmake --build $bdir 2>&1 | Select-String -NotMatch '^\[\d+/\d+\] Building' | Out-Host
exit $LASTEXITCODE
