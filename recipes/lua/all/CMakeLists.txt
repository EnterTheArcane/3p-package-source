#
# Copyright (c) Contributors to the Open 3D Engine Project.
# For complete copyright and license terms please see the LICENSE at the root of this distribution.
#
# SPDX-License-Identifier: Apache-2.0 OR MIT
#

# Lua ships no build system. This builds the static library from the amalgamated
# source and installs the headers under Lua/, because engine code includes
# <Lua/lualib.h> rather than <lua.h>.

cmake_minimum_required(VERSION 3.22)

project(lua C)

file(GLOB LUA_HEADERS "${CMAKE_CURRENT_SOURCE_DIR}/*.h")

add_library(lualib STATIC onelua.c)

# onelua.c builds the interpreter unless told to produce the library instead.
target_compile_definitions(lualib PRIVATE MAKE_LIB)

set_target_properties(lualib PROPERTIES PUBLIC_HEADER "${LUA_HEADERS}")

include(GNUInstallDirs)

install(TARGETS lualib
    PUBLIC_HEADER DESTINATION ${CMAKE_INSTALL_INCLUDEDIR}/Lua
    ARCHIVE       DESTINATION ${CMAKE_INSTALL_LIBDIR}
    LIBRARY       DESTINATION ${CMAKE_INSTALL_LIBDIR}
    RUNTIME       DESTINATION ${CMAKE_INSTALL_BINDIR}
)
