cmake_minimum_required(VERSION 3.15)
project(cityhash LANGUAGES CXX)

include(GNUInstallDirs)

# Upstream ships autotools, which does not cross compile to the platforms the engine
# targets. The library is one translation unit, so it is built directly instead.
add_library(cityhash ${CITYHASH_SRC_DIR}/src/city.cc)
target_include_directories(cityhash PUBLIC ${CITYHASH_SRC_DIR}/src)
set_target_properties(cityhash PROPERTIES WINDOWS_EXPORT_ALL_SYMBOLS ON)

# city.cc includes config.h, which upstream generates with autotools. It reads exactly
# two answers from it, and every platform the engine targets is little endian, so
# WORDS_BIGENDIAN is deliberately left undefined.
if(MSVC)
    file(WRITE ${CMAKE_CURRENT_BINARY_DIR}/config.h "")
else()
    file(WRITE ${CMAKE_CURRENT_BINARY_DIR}/config.h "#define HAVE_BUILTIN_EXPECT 1\n")
endif()
target_include_directories(cityhash PRIVATE ${CMAKE_CURRENT_BINARY_DIR})
target_compile_definitions(cityhash PRIVATE __STDC_FORMAT_MACROS=1)

install(TARGETS cityhash
        RUNTIME DESTINATION ${CMAKE_INSTALL_BINDIR}
        LIBRARY DESTINATION ${CMAKE_INSTALL_LIBDIR}
        ARCHIVE DESTINATION ${CMAKE_INSTALL_LIBDIR})

# Engine code includes <city.h>, so it sits at the root of the include directory.
# citycrc.h is deliberately not shipped: it declares the CRC variants, which only exist
# when the library was compiled with SSE4.2, so offering the header invites a link error.
install(FILES ${CITYHASH_SRC_DIR}/src/city.h DESTINATION ${CMAKE_INSTALL_INCLUDEDIR})
