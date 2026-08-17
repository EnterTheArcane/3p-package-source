#
# Copyright (c) Contributors to the Open 3D Engine Project.
# For complete copyright and license terms please see the LICENSE at the root of this distribution.
#
# SPDX-License-Identifier: Apache-2.0 OR MIT
#

# azslc is a build tool, not a library: nothing links it, the shader builder runs it.
# The package therefore exports an interface target whose only job is to carry the
# executable into the build output.

set(MY_NAME "azslc")
set(TARGET_WITH_NAMESPACE "3rdParty::${MY_NAME}")
if (TARGET ${TARGET_WITH_NAMESPACE})
    return()
endif()

set(${MY_NAME}_BINARY_DIR ${CMAKE_CURRENT_LIST_DIR}/${MY_NAME}/bin)
set(${MY_NAME}_EXECUTABLE ${${MY_NAME}_BINARY_DIR}/Release/azslc${CMAKE_EXECUTABLE_SUFFIX})

add_library(${TARGET_WITH_NAMESPACE} INTERFACE IMPORTED GLOBAL)

# ly_add_target_files is O3DE's; guarded so the package still resolves outside the engine.
if (COMMAND ly_add_target_files)
    ly_add_target_files(
        TARGETS ${TARGET_WITH_NAMESPACE}
        OUTPUT_SUBDIRECTORY "Builders/AZSLc"
        FILES ${${MY_NAME}_EXECUTABLE}
    )
endif()

set(${MY_NAME}_FOUND True)

if (NOT LY_VERSION_ENGINE_NAME)
    message(STATUS "Using the O3DE version of azslc from ${CMAKE_CURRENT_LIST_DIR}")
endif()
