#
# Copyright (c) Contributors to the Open 3D Engine Project.
# For complete copyright and license terms please see the LICENSE at the root of this distribution.
#
# SPDX-License-Identifier: Apache-2.0 OR MIT
#

set(LIB_NAME "ISPCTexComp")
set(TARGET_WITH_NAMESPACE "3rdParty::${LIB_NAME}")
if (TARGET ${TARGET_WITH_NAMESPACE})
    return()
endif()

set(${LIB_NAME}_INCLUDE_DIR ${CMAKE_CURRENT_LIST_DIR}/ispc-texture-compressor/include)
set(${LIB_NAME}_BINARY_DIR ${CMAKE_CURRENT_LIST_DIR}/ispc-texture-compressor/bin)

# Windows links an import library; elsewhere the shared library is linked directly.
if (WIN32)
    set(${LIB_NAME}_LIBRARY ${${LIB_NAME}_BINARY_DIR}/ispc_texcomp.lib)
else()
    set(${LIB_NAME}_LIBRARY
        ${${LIB_NAME}_BINARY_DIR}/${CMAKE_SHARED_LIBRARY_PREFIX}ispc_texcomp${CMAKE_SHARED_LIBRARY_SUFFIX})
endif()

set(${LIB_NAME}_RUNTIME_DEPENDENCIES
    ${${LIB_NAME}_BINARY_DIR}/${CMAKE_SHARED_LIBRARY_PREFIX}ispc_texcomp${CMAKE_SHARED_LIBRARY_SUFFIX})

add_library(${TARGET_WITH_NAMESPACE} INTERFACE IMPORTED GLOBAL)

if (COMMAND ly_target_include_system_directories)
    ly_target_include_system_directories(TARGET ${TARGET_WITH_NAMESPACE} INTERFACE ${${LIB_NAME}_INCLUDE_DIR})
else()
    target_include_directories(${TARGET_WITH_NAMESPACE} SYSTEM INTERFACE ${${LIB_NAME}_INCLUDE_DIR})
endif()

target_link_libraries(${TARGET_WITH_NAMESPACE} INTERFACE ${${LIB_NAME}_LIBRARY})

# The shared library has to sit beside the executable that loads it.
if (COMMAND ly_add_target_files)
    ly_add_target_files(TARGETS ${TARGET_WITH_NAMESPACE} FILES ${${LIB_NAME}_RUNTIME_DEPENDENCIES})
endif()

set(${LIB_NAME}_FOUND True)

if (NOT LY_VERSION_ENGINE_NAME)
    message(STATUS "Using the O3DE version of ${LIB_NAME} from ${CMAKE_CURRENT_LIST_DIR}")
endif()
