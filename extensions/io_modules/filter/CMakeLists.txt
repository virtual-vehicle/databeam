cmake_minimum_required(VERSION 3.15)
project(filter C CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)
option(BUILD_SHARED_LIBS "Build using shared libraries" OFF)
# set(CMAKE_VERBOSE_MAKEFILE ON)

set(ROOT ../../..)
set(SOURCE ${ROOT}/libs/cpp/source)
set(HEADER ${ROOT}/libs/cpp/header)

#  -Wextra -pedantic -Werror
add_compile_options(-Wall)

if(DEFINED ENV{DEBUGGING})
    message("debugging enabled: adding compiler options")
    add_compile_options(-g -ggdb -Og)
else()
    message("debugging disabled")
endif()

find_package(MCAP REQUIRED)
find_package(nlohmann_json REQUIRED)
find_package(RapidJSON REQUIRED)
find_package(cppzmq REQUIRED)

include_directories(${CMAKE_CURRENT_BINARY_DIR})

message(${CMAKE_CURRENT_SOURCE_DIR})

set(SRC_FILES
    main.cpp
    source/filter.cpp
    source/FilterBase.cpp
    source/AverageFilter.cpp
    source/DownsampleAverageFilter.cpp
    source/ExponentialAverageFilter.cpp
    source/MedianFilter.cpp
    ${SOURCE}/ModuleInterface.cpp
    ${SOURCE}/EnvConfig.cpp
    ${SOURCE}/Logger.cpp
    ${SOURCE}/TimeSource.cpp
    ${SOURCE}/Utils.cpp
    ${SOURCE}/IOModule.cpp
    ${SOURCE}/Json.cpp
    ${SOURCE}/JsonWriter.cpp
    ${SOURCE}/DataBroker.cpp
    ${SOURCE}/DataConfig.cpp
    ${SOURCE}/Event.cpp
    ${SOURCE}/NetworkMessages.cpp
    ${SOURCE}/JobEntry.cpp
    ${SOURCE}/JobManager.cpp
    ${SOURCE}/McapSchema.cpp
    ${SOURCE}/ConfigEntry.cpp
    ${SOURCE}/ConfigFactory.cpp
    ${SOURCE}/ConnectionManager.cpp
    ${SOURCE}/ZMQConnectionManager.cpp
    ${SOURCE}/MultiConnectionManager.cpp
)
add_executable(${PROJECT_NAME} ${SRC_FILES})
set_target_properties(${PROJECT_NAME} PROPERTIES OUTPUT_NAME "main")

target_include_directories(${PROJECT_NAME} PRIVATE
    .
    ./header
    ${HEADER}
    ${ROOT}/libs/thirdparty
)

target_link_libraries(${PROJECT_NAME} cppzmq-static)
target_link_libraries(${PROJECT_NAME} mcap::mcap)
target_link_libraries(${PROJECT_NAME} nlohmann_json::nlohmann_json)
target_link_libraries(${PROJECT_NAME} rapidjson)

target_include_directories(${PROJECT_NAME} PUBLIC ${CMAKE_BINARY_DIR})
