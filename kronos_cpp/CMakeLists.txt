# Kronos IDE — Native Qt extensions build configuration
cmake_minimum_required(VERSION 3.18)
project(kronos_native LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)
set(CMAKE_AUTOMOC ON)

find_package(Python3 COMPONENTS Interpreter Development.Module REQUIRED)
find_package(pybind11 CONFIG QUIET)
if(NOT pybind11_FOUND)
    execute_process(
        COMMAND ${Python3_EXECUTABLE} -m pybind11 --cmakedir
        OUTPUT_VARIABLE PYBIND11_CMAKE_DIR
        OUTPUT_STRIP_TRAILING_WHITESPACE
    )
    if(PYBIND11_CMAKE_DIR)
        list(APPEND CMAKE_PREFIX_PATH ${PYBIND11_CMAKE_DIR})
    endif()
    find_package(pybind11 CONFIG REQUIRED)
endif()
find_package(Qt6 REQUIRED COMPONENTS Core Gui Widgets OpenGL OpenGLWidgets)
find_package(Eigen3 QUIET)

option(KRONOS_USE_FFTW "Enable FFTW acceleration for Signal Analyzer" ON)
if(KRONOS_USE_FFTW)
    find_package(PkgConfig QUIET)
    if(PkgConfig_FOUND)
        pkg_check_modules(FFTW3 IMPORTED_TARGET fftw3)
    endif()
endif()

pybind11_add_module(kronos_native MODULE
    bindings.cpp
    src/syntax_highlighter.cpp
    src/waveform_renderer.cpp
    src/canvas_renderer.cpp
    src/vehicle_physics.cpp
)

pybind11_add_module(kronos_physics MODULE
    src/vehicle_physics_bindings.cpp
    src/vehicle_physics.cpp
)

pybind11_add_module(kronos_signal_engine MODULE
    signal_engine/bindings.cpp
    signal_engine/fft_engine.cpp
    signal_engine/stft_engine.cpp
    signal_engine/filter_engine.cpp
    signal_engine/wavelet_engine.cpp
    signal_engine/measurements_engine.cpp
)

# Keep warnings strict for native code quality.
target_compile_options(kronos_native PRIVATE
    -Wall
    -Wextra
    -Wpedantic
)
target_compile_options(kronos_physics PRIVATE
    -Wall
    -Wextra
    -Wpedantic
)
target_compile_options(kronos_signal_engine PRIVATE
    -Wall
    -Wextra
    -Wpedantic
)

target_include_directories(kronos_native PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}/src
)
target_include_directories(kronos_signal_engine PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}
)

target_link_libraries(kronos_native PRIVATE
    Qt6::Core
    Qt6::Gui
    Qt6::Widgets
    Qt6::OpenGL
    Qt6::OpenGLWidgets
)
if(Eigen3_FOUND)
    target_link_libraries(kronos_signal_engine PRIVATE Eigen3::Eigen)
endif()
if(KRONOS_USE_FFTW AND FFTW3_FOUND)
    target_compile_definitions(kronos_signal_engine PRIVATE KRONOS_USE_FFTW)
    target_link_libraries(kronos_signal_engine PRIVATE PkgConfig::FFTW3)
endif()

set_target_properties(kronos_native PROPERTIES
    LIBRARY_OUTPUT_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}/../kronos/native
    RUNTIME_OUTPUT_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}/../kronos/native
)

set_target_properties(kronos_physics PROPERTIES
    LIBRARY_OUTPUT_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}/../kronos/native
    RUNTIME_OUTPUT_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}/../kronos/native
)

set_target_properties(kronos_signal_engine PROPERTIES
    LIBRARY_OUTPUT_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}/../kronos/native
    RUNTIME_OUTPUT_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}/../kronos/native
)
