#
# Copyright (c) Contributors to the Open 3D Engine Project.
# For complete copyright and license terms please see the LICENSE at the root of this distribution.
#
# SPDX-License-Identifier: Apache-2.0 OR MIT
#

set(MY_NAME "NvCloth")
set(TARGET_WITH_NAMESPACE "3rdParty::${MY_NAME}")
if (TARGET ${TARGET_WITH_NAMESPACE})
    return()
endif()

set(${MY_NAME}_BASE ${CMAKE_CURRENT_LIST_DIR}/nvcloth)

set(${MY_NAME}_INCLUDE_DIR ${${MY_NAME}_BASE}/NvCloth/include
                           ${${MY_NAME}_BASE}/NvCloth/extensions/include
                           ${${MY_NAME}_BASE}/PxShared/include)

# These have to be defined and empty rather than given a value: NvCloth uses them as a
# prefix on class and function declarations, so anything else is a syntax error at the
# point of use.
set(${MY_NAME}_COMPILE_DEFINITIONS NV_CLOTH_IMPORT= PX_CALL_CONV=)

# One library per configuration, named after it in upper case, except release which
# carries no suffix. The engine's profile build therefore asks for NvClothPROFILE.
set(${MY_NAME}_LIBRARY
    ${${MY_NAME}_BASE}/NvCloth/lib/${CMAKE_STATIC_LIBRARY_PREFIX}NvCloth$<$<NOT:$<CONFIG:Release>>:$<UPPER_CASE:$<CONFIG>>>${CMAKE_STATIC_LIBRARY_SUFFIX})

add_library(${TARGET_WITH_NAMESPACE} INTERFACE IMPORTED GLOBAL)

if (COMMAND ly_target_include_system_directories)
    ly_target_include_system_directories(TARGET ${TARGET_WITH_NAMESPACE} INTERFACE ${${MY_NAME}_INCLUDE_DIR})
else()
    target_include_directories(${TARGET_WITH_NAMESPACE} SYSTEM INTERFACE ${${MY_NAME}_INCLUDE_DIR})
endif()

target_link_libraries(${TARGET_WITH_NAMESPACE} INTERFACE ${${MY_NAME}_LIBRARY})
target_compile_definitions(${TARGET_WITH_NAMESPACE} INTERFACE ${${MY_NAME}_COMPILE_DEFINITIONS})

if (DEFINED ${MY_NAME}_LINK_OPTIONS)
    target_link_options(${TARGET_WITH_NAMESPACE} INTERFACE ${${MY_NAME}_LINK_OPTIONS})
endif()

if (NOT LY_VERSION_ENGINE_NAME)
    message(STATUS "Using the O3DE version of ${MY_NAME} from ${CMAKE_CURRENT_LIST_DIR}")
endif()

set(${MY_NAME}_FOUND True)
