cmake_minimum_required(VERSION 3.15)
project(mikktspace LANGUAGES C)

include(GNUInstallDirs)

add_library(mikktspace ${MIKKTSPACE_SRC_DIR}/mikktspace.c)
target_include_directories(mikktspace PUBLIC ${MIKKTSPACE_SRC_DIR})
set_target_properties(mikktspace PROPERTIES WINDOWS_EXPORT_ALL_SYMBOLS ON)

install(
    TARGETS mikktspace
    RUNTIME DESTINATION ${CMAKE_INSTALL_BINDIR}
    LIBRARY DESTINATION ${CMAKE_INSTALL_LIBDIR}
    ARCHIVE DESTINATION ${CMAKE_INSTALL_LIBDIR}
)

# Under mikkelsen/, which is how the engine includes it.
install(FILES ${MIKKTSPACE_SRC_DIR}/mikktspace.h
        DESTINATION ${CMAKE_INSTALL_INCLUDEDIR}/mikkelsen)
