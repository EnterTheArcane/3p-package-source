#
# Copyright (c) Contributors to the Open 3D Engine Project.
# For complete copyright and license terms please see the LICENSE at the root of this distribution.
#
# SPDX-License-Identifier: Apache-2.0 OR MIT
#

# Derived from the Conan Center lua recipe's CMake wrapper. Lua does not ship a
# CMake build system of its own.

cmake_minimum_required(VERSION 3.15)
project(lua)

set(SOURCE_DIR ${LUA_SRC_DIR})

file(GLOB SRC_LIBLUA "${SOURCE_DIR}/src/*.c")
set(SRC_LUAI "${SOURCE_DIR}/src/lua.c")
set(SRC_LUAC "${SOURCE_DIR}/src/luac.c")
list(REMOVE_ITEM SRC_LIBLUA ${SRC_LUAC} ${SRC_LUAI})

if(COMPILE_AS_CPP)
    set_source_files_properties(${SRC_LIBLUA} ${SRC_LUAI} ${SRC_LUAC}
        PROPERTIES LANGUAGE CXX)
else()
    set(CMAKE_C_STANDARD 99)
endif()

if(WIN32)
    add_definitions(-D_CRT_SECURE_NO_WARNINGS)
endif()

# O3DE keeps iOS on Lua's portable configuration because the POSIX feature set
# enables APIs that are unavailable in an application sandbox.
if(UNIX)
    if(NOT ANDROID AND NOT CMAKE_SYSTEM_NAME STREQUAL "iOS")
        add_definitions(-DLUA_USE_POSIX)
    endif()
    find_library(LIB_MATH NAMES m)
    if(LIB_MATH)
        link_libraries(${LIB_MATH})
    endif()
endif()

add_library(lua ${SRC_LIBLUA})
if(COMPILE_AS_CPP)
    set_target_properties(lua PROPERTIES OUTPUT_NAME "lua-c++")
endif()

if(BUILD_SHARED_LIBS AND WIN32)
    target_compile_definitions(lua PUBLIC -DLUA_BUILD_AS_DLL)
endif()

if(UNIX)
    if(APPLE)
        if(NOT CMAKE_SYSTEM_NAME STREQUAL "iOS")
            target_compile_definitions(lua PUBLIC -DLUA_USE_DLOPEN)
        endif()
    else()
        find_library(LIB_DLOPEN NAMES dl)
        if(LIB_DLOPEN)
            target_compile_definitions(lua PUBLIC -DLUA_USE_DLOPEN)
            target_link_libraries(lua ${LIB_DLOPEN})
        endif()
    endif()
endif()

include(GNUInstallDirs)

install(TARGETS lua
    RUNTIME DESTINATION ${CMAKE_INSTALL_BINDIR}
    LIBRARY DESTINATION ${CMAKE_INSTALL_LIBDIR}
    ARCHIVE DESTINATION ${CMAKE_INSTALL_LIBDIR}
)

if(NOT SKIP_INSTALL_TOOLS)
    # luac consumes private APIs, so it must compile the library sources directly.
    add_executable(luac ${SRC_LUAC} ${SRC_LIBLUA})
    add_executable(luai ${SRC_LUAI})
    target_link_libraries(luai lua)
    set_target_properties(luai PROPERTIES OUTPUT_NAME lua PDB_NAME luai)
    if(WITH_READLINE)
        find_package(readline REQUIRED CONFIG)
        target_compile_definitions(luai PUBLIC -DLUA_USE_READLINE)
        target_link_libraries(luai readline::readline)
    endif()
    install(TARGETS luai luac RUNTIME DESTINATION ${CMAKE_INSTALL_BINDIR})
endif()

install(FILES
    ${SOURCE_DIR}/src/lualib.h
    ${SOURCE_DIR}/src/lua.h
    ${SOURCE_DIR}/src/luaconf.h
    ${SOURCE_DIR}/src/lauxlib.h
    DESTINATION ${CMAKE_INSTALL_INCLUDEDIR}
)
if(NOT COMPILE_AS_CPP)
    install(FILES ${SOURCE_DIR}/src/lua.hpp DESTINATION ${CMAKE_INSTALL_INCLUDEDIR})
endif()
