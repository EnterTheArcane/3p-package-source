#
# Copyright (c) Contributors to the Open 3D Engine Project.
# For complete copyright and license terms please see the LICENSE at the root of this distribution.
#
# SPDX-License-Identifier: Apache-2.0 OR MIT
#

import os

from conan import ConanFile
from conan.tools.cmake import CMake, CMakeToolchain, cmake_layout
from conan.tools.files import apply_conandata_patches, copy, export_conandata_patches, get


class SquishCcrConan(ConanFile):
    """The squish-ccr fork of libsquish, which is what the texture compressor uses.

    Conan Center's libsquish is the original library. squish-ccr is a fork with a
    different and larger API, and engine code includes <squish-ccr/squish.h> and calls
    into that API, so the two are not interchangeable.

    Upstream pins to a commit rather than a release; it has had none, and it ships no
    build system either, so the CMakeLists beside this recipe is the one that builds it.
    On ARM the SSE intrinsics it is written against are translated by sse2neon.
    """

    name = "squish-ccr"
    version = "deb557d"
    description = "squish-ccr, a fork of libsquish with additional block compressors"
    homepage = "https://github.com/Ethatron/squish-ccr"
    license = "MIT"
    package_type = "shared-library"

    settings = "os", "arch", "compiler", "build_type"

    exports_sources = "CMakeLists.txt", "LICENSE.txt"

    def export_sources(self):
        export_conandata_patches(self)
        copy(self, "CMakeLists.txt", self.recipe_folder, self.export_sources_folder)
        copy(self, "LICENSE.txt", self.recipe_folder, self.export_sources_folder)

    def layout(self):
        cmake_layout(self, src_folder="src")

    def source(self):
        get(self, **self.conan_data["sources"][self.version], strip_root=True)
        copy(self, "CMakeLists.txt", self.export_sources_folder, self.source_folder)
        copy(self, "LICENSE.txt", self.export_sources_folder, self.source_folder)

    def generate(self):
        toolchain = CMakeToolchain(self)
        toolchain.cache_variables["CMAKE_BUILD_TYPE"] = "Release"
        toolchain.cache_variables["BUILD_SHARED_LIBS"] = True
        toolchain.extra_cxxflags.append("-Wno-shorten-64-to-32")
        # The CMakeLists picks its SIMD path from CMAKE_SYSTEM_PROCESSOR, which CMake
        # only fills in when cross building. Without it a native ARM build takes the x86
        # branch and fails on <xmmintrin.h>.
        if str(self.settings.arch) in ("armv8", "armv8.3"):
            toolchain.cache_variables["CMAKE_SYSTEM_PROCESSOR"] = "arm64"
        toolchain.generate()

    def build(self):
        apply_conandata_patches(self)

        if str(self.settings.arch) in ("armv8", "armv8.3"):
            # squish-ccr is written against SSE; sse2neon maps those intrinsics to NEON.
            staging = os.path.join(self.build_folder, "sse2neon")
            get(self, **self.conan_data["sse2neon"], destination=staging, strip_root=True)
            copy(self, "sse2neon.h", staging, self.source_folder)
            copy(self, "LICENSE", staging,
                 os.path.join(self.package_folder, "licenses"))

            # The sources include <xmmintrin.h> and friends by name. sse2neon supplies
            # the implementations but not those header names, so each is shimmed to it.
            # The source directory comes first on the include path, so these are found
            # ahead of the compiler's x86-only versions.
            for header in ("xmmintrin.h", "emmintrin.h", "pmmintrin.h",
                           "smmintrin.h", "tmmintrin.h", "nmmintrin.h", "immintrin.h"):
                with open(os.path.join(self.source_folder, header), "w") as handle:
                    handle.write('#pragma once\n#include "sse2neon.h"\n')

        cmake = CMake(self)
        cmake.configure()
        cmake.build()

    def package(self):
        # Headers arrive under squish-ccr/ because that is how engine code includes them.
        include = os.path.join(self.package_folder, "include", "squish-ccr")
        for pattern in ("*.h", "*.inl"):
            copy(self, pattern, self.source_folder, include, keep_path=False)

        for pattern in ("*.dylib", "*.so*", "*.dll", "*.lib", "*.a"):
            copy(self, pattern, self.build_folder,
                 os.path.join(self.package_folder, "bin"), keep_path=False)

        for name in ("LICENSE.txt", "LICENSE*"):
            copy(self, name, self.source_folder,
                 os.path.join(self.package_folder, "licenses"))

    def package_info(self):
        self.cpp_info.libdirs = ["bin"]
        self.cpp_info.bindirs = ["bin"]
        self.cpp_info.libs = ["squish-ccr"]
