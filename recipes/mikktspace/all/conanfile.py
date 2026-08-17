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
from conan.tools.files import get, save


class MikkTSpaceConan(ConanFile):
    name = "mikktspace"
    version = "cci.20200325"
    license = "Zlib"
    package_type = "static-library"

    settings = "os", "arch", "compiler", "build_type"
    options = {"fPIC": [True, False]}
    default_options = {"fPIC": True}

    exports_sources = "CMakeLists.txt"

    def validate(self):
        if str(self.settings.os) not in ("Windows", "Linux", "Macos", "Android", "iOS"):
            raise ConanInvalidConfiguration(f"mikktspace is not shipped for {self.settings.os}")

    def config_options(self):
        if self.settings.os == "Windows":
            del self.options.fPIC

    def configure(self):
        # A C library; the C++ subsettings would only split the package id.
        self.settings.rm_safe("compiler.cppstd")
        self.settings.rm_safe("compiler.libcxx")

    def layout(self):
        cmake_layout(self, src_folder="src")

    def source(self):
        get(self, **self.conan_data["sources"][self.version],
            destination=self.source_folder, strip_root=True)

    def generate(self):
        toolchain = CMakeToolchain(self)
        toolchain.variables["MIKKTSPACE_SRC_DIR"] = self.source_folder.replace("\\", "/")
        toolchain.generate()

    def build(self):
        cmake = CMake(self)
        cmake.configure(build_script_folder=os.path.join(self.source_folder, os.pardir))
        cmake.build()

    def package(self):
        # Upstream ships no license file; the terms are the comment block at the top of
        # the header, which is where Conan Center takes them from too.
        header = os.path.join(self.source_folder, "mikktspace.h")
        with open(header, encoding="utf8") as handle:
            lines = handle.readlines()
        save(self, os.path.join(self.package_folder, "licenses", "LICENSE"),
             "\n".join(line[4:-1] for line in lines[4:21]))

        cmake = CMake(self)
        cmake.install()

    def package_info(self):
        self.cpp_info.set_property("cmake_file_name", "mikkelsen")
        self.cpp_info.libs = ["mikktspace"]
