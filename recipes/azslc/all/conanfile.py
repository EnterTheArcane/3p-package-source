#
# Copyright (c) Contributors to the Open 3D Engine Project.
# For complete copyright and license terms please see the LICENSE at the root of this distribution.
#
# SPDX-License-Identifier: Apache-2.0 OR MIT
#

import os

from conan import ConanFile
from conan.errors import ConanInvalidConfiguration
from conan.tools.cmake import CMake, CMakeToolchain, cmake_layout
from conan.tools.files import copy, get


class AzslcConan(ConanFile):
    name = "azslc"
    version = "1.8.22"

    license = "Apache-2.0 OR MIT"
    package_type = "application"

    settings = "os", "arch", "compiler", "build_type"

    def validate(self):
        if str(self.settings.os) not in ("Windows", "Linux", "Macos"):
            raise ConanInvalidConfiguration(
                f"azslc is a host tool and is not built for {self.settings.os}"
            )

    def layout(self):
        cmake_layout(self, src_folder="src")

    def source(self):
        get(self, **self.conan_data["sources"][self.version], strip_root=True)

    def generate(self):
        toolchain = CMakeToolchain(self)
        toolchain.cache_variables["CMAKE_BUILD_TYPE"] = "Release"
        toolchain.generate()

    def build(self):
        cmake = CMake(self)
        # The CMake project lives in src/, not at the repository root. Upstream's
        # prepare_solution_<platform> scripts do nothing more than this.
        cmake.configure(build_script_folder="src")
        cmake.build(target="azslc")

    def package(self):
        suffix = ".exe" if self.settings.os == "Windows" else ""
        # bin/Release is where the engine's shader builder looks for it.
        copy(self, f"azslc{suffix}", self.build_folder,
             os.path.join(self.package_folder, "bin", "Release"), keep_path=False)
        for name in ("LICENSE.txt", "LICENSE_APACHE2.TXT", "LICENSE_MIT.TXT", "README.md"):
            copy(self, name, self.source_folder,
                 os.path.join(self.package_folder, "licenses"))

    def package_info(self):
        self.cpp_info.set_property("cmake_file_name", "azslc")
        self.cpp_info.includedirs = []
        self.cpp_info.libdirs = []
        self.cpp_info.bindirs = ["bin/Release"]

    def package_id(self):
        # A tool: the compiler used to build it does not change what it does.
        del self.info.settings.compiler
        del self.info.settings.build_type
