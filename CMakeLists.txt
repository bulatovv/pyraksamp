cmake_minimum_required(VERSION 3.20)
project(pyraksamp_core CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# ── Corrosion: integrate Rust crate ──────────────────────────────────────────
include(FetchContent)
FetchContent_Declare(Corrosion
    GIT_REPOSITORY https://github.com/corrosion-rs/corrosion.git
    GIT_TAG v0.5)
FetchContent_MakeAvailable(Corrosion)
corrosion_import_crate(MANIFEST_PATH src/samp_rust/Cargo.toml)

set(PYBIND11_FINDPYTHON ON)
find_package(pybind11 REQUIRED)

set(SOURCES
    src/samp_core/encrypt.cpp
    src/samp_core/reliability.cpp
    src/samp_core/client.cpp
    src/samp_core/bindings.cpp
)

pybind11_add_module(_core ${SOURCES})

target_include_directories(_core PRIVATE src/samp_core)
target_link_libraries(_core PRIVATE samp_rust-static)

if(WIN32)
    target_link_libraries(_core PRIVATE ws2_32)
endif()

# Install into the pyraksamp package
install(TARGETS _core DESTINATION pyraksamp)

option(SAMP_BUILD_TESTS "Build internal test bindings module (_core_test)" OFF)
if(SAMP_BUILD_TESTS)
    pybind11_add_module(_core_test
        src/samp_core/encrypt.cpp
        src/samp_core/reliability.cpp
        tests/bindings_test.cpp
    )
    target_include_directories(_core_test PRIVATE src/samp_core)
    target_link_libraries(_core_test PRIVATE samp_rust-static)
    if(WIN32)
        target_link_libraries(_core_test PRIVATE ws2_32)
    endif()
    # Install at site-packages root so it's importable as `import _core_test`
    install(TARGETS _core_test DESTINATION .)
endif()
