cmake_minimum_required(VERSION 3.20)
project(C12Recomp C CXX ASM_MASM)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_MSVC_RUNTIME_LIBRARY "MultiThreaded")

# C12_REGION: PAL (SCES-03364, gen/) or USA (SCUS-94666, gen_usa/, c12_usa.exe). The runtime and mods keep
# PAL addresses; a USA build translates them (runtime/region.cpp, table from tools/region_map.py).
set(C12_REGION "PAL" CACHE STRING "PAL or USA")
if(C12_REGION STREQUAL "USA")
    set(GEN_DIR ${CMAKE_SOURCE_DIR}/gen_usa)
    set(EXE_NAME c12_usa)
    add_compile_definitions(C12_USA=1)
else()
    set(GEN_DIR ${CMAKE_SOURCE_DIR}/gen)
    set(EXE_NAME c12)
endif()
file(GLOB GEN_SRC CONFIGURE_DEPENDS ${GEN_DIR}/*.c)
file(GLOB RT_SRC CONFIGURE_DEPENDS ${CMAKE_SOURCE_DIR}/runtime/*.cpp)
file(GLOB IMGUI_SRC ${CMAKE_SOURCE_DIR}/third_party/imgui/*.cpp)

add_library(c12gen OBJECT ${GEN_SRC})
target_include_directories(c12gen PRIVATE ${CMAKE_SOURCE_DIR}/runtime ${GEN_DIR})
# generated code: optimise, no warnings noise, no stack checks
target_compile_options(c12gen PRIVATE /O2 /Ob1 /GS- /w /Gy)

add_executable(c12 ${RT_SRC} ${CMAKE_SOURCE_DIR}/runtime/ctxswitch.asm ${IMGUI_SRC} $<TARGET_OBJECTS:c12gen>)
target_include_directories(c12 PRIVATE ${CMAKE_SOURCE_DIR}/runtime ${CMAKE_SOURCE_DIR}/third_party/imgui)
target_compile_options(c12 PRIVATE $<$<COMPILE_LANGUAGE:CXX>:/O2 /GS- /W3 /wd4244 /wd4267 /wd4996 /wd4018 /wd4554 /D_CRT_SECURE_NO_WARNINGS>)
target_link_libraries(c12 PRIVATE xinput winmm d3d11 dxgi d3dcompiler ole32 user32 gdi32 comdlg32)
# GUI program (no console window on double-click); still a normal main()
# save states copy native stacks holding return addresses: c12.exe must always load at the same
# address (no ASLR) and the stacks are switched by hand (no CET shadow stack)
set_target_properties(c12 PROPERTIES OUTPUT_NAME ${EXE_NAME})
target_link_options(c12 PRIVATE /STACK:67108864 /SUBSYSTEM:WINDOWS /ENTRY:mainCRTStartup /DYNAMICBASE:NO /CETCOMPAT:NO /PDBALTPATH:${EXE_NAME}.pdb)
# a copy next to c12.ini so it can simply be double-clicked from the project folder
add_custom_command(TARGET c12 POST_BUILD COMMAND ${CMAKE_COMMAND} -E copy $<TARGET_FILE:c12> ${CMAKE_SOURCE_DIR}/${EXE_NAME}.exe)
