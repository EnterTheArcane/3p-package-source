#
# Copyright (c) Contributors to the Open 3D Engine Project.
# For complete copyright and license terms please see the LICENSE at the root of this distribution.
#
# SPDX-License-Identifier: Apache-2.0 OR MIT
#

# The shader compiler is run by the shader builder rather than linked, so this exports
# an interface target that carries the executables and the compiler library into the
# build output. Nothing here is on a link line.

set(MY_NAME "DirectXShaderCompilerDxc")
set(TARGET_WITH_NAMESPACE "3rdParty::${MY_NAME}")
if (TARGET ${TARGET_WITH_NAMESPACE})
    return()
endif()

set(output_subfolder "Builders/DirectXShaderCompiler")
set(${MY_NAME}_BINARY_DIR ${CMAKE_CURRENT_LIST_DIR}/dxc/bin)
set(${MY_NAME}_LIB_DIR ${CMAKE_CURRENT_LIST_DIR}/dxc/lib)

add_library(${TARGET_WITH_NAMESPACE} INTERFACE IMPORTED GLOBAL)

# Which files exist differs by platform: Windows ships DLLs beside the executables,
# everything else keeps the shared library in lib/.
file(GLOB ${MY_NAME}_BIN_RUNTIME_DEPENDENCIES
    "${${MY_NAME}_BINARY_DIR}/dxc*"
    "${${MY_NAME}_BINARY_DIR}/dxsc*"
    "${${MY_NAME}_BINARY_DIR}/*.dll"
)
file(GLOB ${MY_NAME}_LIB_RUNTIME_DEPENDENCIES
    "${${MY_NAME}_LIB_DIR}/*dxcompiler*"
)

if (COMMAND ly_add_target_files)
    if (${MY_NAME}_BIN_RUNTIME_DEPENDENCIES)
        ly_add_target_files(TARGETS ${TARGET_WITH_NAMESPACE}
            OUTPUT_SUBDIRECTORY "${output_subfolder}/bin"
            FILES ${${MY_NAME}_BIN_RUNTIME_DEPENDENCIES})
    endif()
    if (${MY_NAME}_LIB_RUNTIME_DEPENDENCIES)
        ly_add_target_files(TARGETS ${TARGET_WITH_NAMESPACE}
            OUTPUT_SUBDIRECTORY "${output_subfolder}/lib"
            FILES ${${MY_NAME}_LIB_RUNTIME_DEPENDENCIES})
    endif()
endif()

set(${MY_NAME}_FOUND True)

if (NOT LY_VERSION_ENGINE_NAME)
    message(STATUS "Using the O3DE version of ${MY_NAME} from ${CMAKE_CURRENT_LIST_DIR}")
endif()
