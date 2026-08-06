#
# Copyright (c) Contributors to the Open 3D Engine Project.
# For complete copyright and license terms please see the LICENSE at the root of this distribution.
#
# SPDX-License-Identifier: Apache-2.0 OR MIT
#

import os

from conan import ConanFile
from conan.tools.cmake import CMake, CMakeToolchain, cmake_layout
from conan.tools.files import copy, get, replace_in_file


class AstcEncoderConan(ConanFile):
    name = "astc-encoder"
    version = "3.2"
    rev = 1
    platforms = "desktop"
    license = "Apache-2.0"
    package_type = "static-library"

    settings = "os", "arch", "compiler", "build_type"

    @property
    def _isa(self):
        # NEON on Apple Silicon and other ARM hosts, SSE4.1 elsewhere.
        return "NEON" if str(self.settings.arch) in ("armv8", "armv8.3") else "SSE41"

    @property
    def _suffix(self):
        return "neon" if self._isa == "NEON" else "sse4.1"

    def layout(self):
        cmake_layout(self, src_folder="src")

    def source(self):
        get(self, **self.conan_data["sources"][self.version], strip_root=True)

    def generate(self):
        toolchain = CMakeToolchain(self)
        toolchain.cache_variables[f"ISA_{self._isa}"] = True
        toolchain.cache_variables["CMAKE_BUILD_TYPE"] = "Release"
        toolchain.generate()

    def build(self):
        # The project compiles with -Werror against a warning set from 2021. Newer
        # compilers flag code it was clean against, so the promotion is dropped rather
        # than chasing each new warning; a suppression flag cannot win because -Werror
        # is applied per target, after CMAKE_CXX_FLAGS.
        replace_in_file(self, os.path.join(self.source_folder, "Source", "cmake_core.cmake"),
                        "$<$<NOT:$<CXX_COMPILER_ID:MSVC>>:-Werror>", "", strict=False)

        cmake = CMake(self)
        cmake.configure()
        cmake.build()

    def package(self):
        copy(self, "astcenc.h", os.path.join(self.source_folder, "Source"),
             os.path.join(self.package_folder, "include"))
        copy(self, "LICENSE.txt", self.source_folder,
             os.path.join(self.package_folder, "licenses"))
        for pattern in ("*.a", "*.lib", "astcenc-*"):
            copy(self, pattern, self.build_folder,
                 os.path.join(self.package_folder, "bin"), keep_path=False)

    def package_info(self):
        self.cpp_info.set_property("cmake_file_name", "astc-encoder")
        self.cpp_info.libdirs = ["bin"]
        self.cpp_info.bindirs = ["bin"]
        self.cpp_info.libs = [f"astcenc-{self._suffix}-static"]
