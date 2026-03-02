cmake_minimum_required(VERSION 3.20)
project(pyraksamp_core CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

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

if(WIN32)
    target_link_libraries(_core PRIVATE ws2_32)
endif()

# Install into the pyraksamp package
install(TARGETS _core DESTINATION pyraksamp)
