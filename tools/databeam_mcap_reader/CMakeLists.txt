cmake_minimum_required(VERSION 3.15)
project(_core LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)

add_compile_options(-Wall)

# avoid warning: "lto-wrapper: warning: using serial compilation of 6 LTRANS jobs"
add_compile_options("-flto=4")
set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -flto=4")

if(DEFINED DEBUG_OUTPUT)
    add_compile_definitions(DEBUG_OUTPUT=${DEBUG_OUTPUT})
endif()

# C++ libs, by conan
find_package(MCAP REQUIRED)
find_package(RapidJSON REQUIRED)

find_package(pybind11 CONFIG REQUIRED)
pybind11_add_module(${PROJECT_NAME} src/parse_mcap.cpp)

target_link_libraries(${PROJECT_NAME} PRIVATE
    mcap::mcap
    rapidjson
)

install(TARGETS ${PROJECT_NAME} LIBRARY DESTINATION databeam_mcap_reader)

if(WIN32)
    set(MCAP_CLI_NAME mcap_cli.exe)
else()
    set(MCAP_CLI_NAME mcap_cli)
endif()

# Install Python source files
install(FILES
    src/databeam_mcap_reader/__init__.py
    src/databeam_mcap_reader/__init__.pyi
    src/databeam_mcap_reader/reader.py
    src/databeam_mcap_reader/collector.py
    DESTINATION databeam_mcap_reader
)

install(PROGRAMS
    ./${MCAP_CLI_NAME}
    DESTINATION databeam_mcap_reader
)
