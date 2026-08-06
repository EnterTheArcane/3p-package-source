#
# Copyright (c) Contributors to the Open 3D Engine Project.
# For complete copyright and license terms please see the LICENSE at the root of this distribution.
#
# SPDX-License-Identifier: Apache-2.0 OR MIT
#

import os

from conan import ConanFile
from conan.tools.cmake import CMake, CMakeToolchain, cmake_layout
from conan.tools.files import get, save


class MikkTSpaceConan(ConanFile):
    """MikkTSpace with its header under mikkelsen/.

    Conan Center installs mikktspace.h at the root of the include directory. Engine code
    includes <mikkelsen/mikktspace.h>, after the author rather than the library, so the
    header is nested here to match. Everything else follows Conan Center's recipe: the
    same upstream commit, and the library built from the one source file.
    """

    name = "mikktspace"
    version = "cci.20200325"
    description = "A common standard for tangent space used in baking tools to produce normal maps"
    homepage = "https://github.com/mmikk/MikkTSpace"
    license = "Zlib"
    package_type = "static-library"

    settings = "os", "arch", "compiler", "build_type"
    options = {"fPIC": [True, False]}
    default_options = {"fPIC": True}

    exports_sources = "CMakeLists.txt"

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
        self.cpp_info.libs = ["mikktspace"]
