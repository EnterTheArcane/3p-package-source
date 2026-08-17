#
# Copyright (c) Contributors to the Open 3D Engine Project.
# For complete copyright and license terms please see the LICENSE at the root of this distribution.
#
# SPDX-License-Identifier: Apache-2.0 OR MIT
#

set(MY_NAME "OpenImageIO")
set(TARGET_WITH_NAMESPACE "3rdParty::${MY_NAME}")
if (TARGET ${TARGET_WITH_NAMESPACE})
    return()
endif()

set(${MY_NAME}_BASE      ${CMAKE_CURRENT_LIST_DIR}/openimageio)
set(${MY_NAME}_INCLUDE_DIR ${${MY_NAME}_BASE}/include)
set(${MY_NAME}_BIN_DIR   ${${MY_NAME}_BASE}/bin)
set(${MY_NAME}_LIB_DIR   ${${MY_NAME}_BASE}/lib)

# Pick the file a consumer will actually record a dependency on.
#
# A shared OpenImageIO ships as three names: the real libOpenImageIO.3.1.16.dylib and
# two symlinks, libOpenImageIO.3.1.dylib and libOpenImageIO.dylib. Its install name is
# the middle one, so that is the name that ends up inside anything linked against it,
# and that is the name that has to exist beside the executable at run time. Linking the
# fully versioned file instead leaves the engine copying a name nothing asks for, and
# the bundle fails to resolve @rpath/libOpenImageIO.3.1.dylib.
#
# The install name is the shortest of the versioned names, so that is what is chosen.
function(_openimageio_library out_variable stem)
    file(GLOB versioned
        "${${MY_NAME}_LIB_DIR}/${CMAKE_SHARED_LIBRARY_PREFIX}${stem}.*${CMAKE_SHARED_LIBRARY_SUFFIX}")
    set(best "")
    foreach(candidate IN LISTS versioned)
        string(LENGTH "${candidate}" candidate_length)
        if (best STREQUAL "" OR candidate_length LESS best_length)
            set(best "${candidate}")
            set(best_length ${candidate_length})
        endif()
    endforeach()

    if (best STREQUAL "")
        # Unversioned shared, or a static build; either resolves to a single file.
        file(GLOB best
            "${${MY_NAME}_LIB_DIR}/${CMAKE_SHARED_LIBRARY_PREFIX}${stem}${CMAKE_SHARED_LIBRARY_SUFFIX}"
            "${${MY_NAME}_LIB_DIR}/${CMAKE_STATIC_LIBRARY_PREFIX}${stem}${CMAKE_STATIC_LIBRARY_SUFFIX}")
        list(GET best 0 best)
    endif()
    set(${out_variable} "${best}" PARENT_SCOPE)
endfunction()

_openimageio_library(${MY_NAME}_LIBRARY OpenImageIO)
if (NOT ${MY_NAME}_LIBRARY)
    message(FATAL_ERROR "No OpenImageIO library found in ${${MY_NAME}_LIB_DIR}")
endif()

if (${MY_NAME}_LIBRARY MATCHES "${CMAKE_STATIC_LIBRARY_SUFFIX}$")
    add_library(${TARGET_WITH_NAMESPACE} STATIC IMPORTED GLOBAL)
else()
    add_library(${TARGET_WITH_NAMESPACE} SHARED IMPORTED GLOBAL)
endif()
set_target_properties(${TARGET_WITH_NAMESPACE} PROPERTIES
    IMPORTED_LOCATION "${${MY_NAME}_LIBRARY}")

# OpenImageIO is two libraries. The classes marked OIIO_UTIL_API -- ParamValue and what
# builds on it, which ImageSpec's inline destructor calls -- live in OpenImageIO_Util,
# so linking only OpenImageIO leaves those symbols undefined in the consumer. It is an
# imported target rather than a bare path so that the engine treats it as a library to
# deploy, not just something to put on a link line.
_openimageio_library(${MY_NAME}_UTIL_LIBRARY OpenImageIO_Util)
if (NOT ${MY_NAME}_UTIL_LIBRARY)
    message(FATAL_ERROR "No OpenImageIO_Util library found in ${${MY_NAME}_LIB_DIR}")
endif()

if (${MY_NAME}_UTIL_LIBRARY MATCHES "${CMAKE_STATIC_LIBRARY_SUFFIX}$")
    add_library(3rdParty::${MY_NAME}::Util STATIC IMPORTED GLOBAL)
else()
    add_library(3rdParty::${MY_NAME}::Util SHARED IMPORTED GLOBAL)
endif()
set_target_properties(3rdParty::${MY_NAME}::Util PROPERTIES
    IMPORTED_LOCATION "${${MY_NAME}_UTIL_LIBRARY}")
set_target_properties(${TARGET_WITH_NAMESPACE} PROPERTIES
    INTERFACE_LINK_LIBRARIES "3rdParty::${MY_NAME}::Util")

if (COMMAND ly_target_include_system_directories)
    ly_target_include_system_directories(TARGET ${TARGET_WITH_NAMESPACE} INTERFACE ${${MY_NAME}_INCLUDE_DIR})
else()
    target_include_directories(${TARGET_WITH_NAMESPACE} SYSTEM INTERFACE ${${MY_NAME}_INCLUDE_DIR})
endif()

# The asset pipeline runs oiiotool and friends, and imports the Python bindings, rather
# than linking them. They travel as interface targets whose only job is deployment.
add_library(3rdParty::${MY_NAME}::Tools::Binaries INTERFACE IMPORTED GLOBAL)
add_library(3rdParty::${MY_NAME}::Tools::PythonPlugins INTERFACE IMPORTED GLOBAL)

file(GLOB ${MY_NAME}_TOOL_BINARIES "${${MY_NAME}_BIN_DIR}/*")
file(GLOB_RECURSE ${MY_NAME}_PYTHON_PLUGINS "${${MY_NAME}_LIB_DIR}/python*/site-packages/*")

if (COMMAND ly_add_target_files)
    if (${MY_NAME}_TOOL_BINARIES)
        ly_add_target_files(TARGETS 3rdParty::${MY_NAME}::Tools::Binaries
            FILES ${${MY_NAME}_TOOL_BINARIES})
    endif()
    if (${MY_NAME}_PYTHON_PLUGINS)
        ly_add_target_files(TARGETS 3rdParty::${MY_NAME}::Tools::PythonPlugins
            FILES ${${MY_NAME}_PYTHON_PLUGINS})
    endif()
endif()

set(${MY_NAME}_FOUND True)

if (NOT LY_VERSION_ENGINE_NAME)
    message(STATUS "Using the O3DE version of ${MY_NAME} from ${CMAKE_CURRENT_LIST_DIR}")
endif()
