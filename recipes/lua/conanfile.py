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


class LuaConan(ConanFile):
    name = "lua"
    version = "5.4.4"
    rev = 1
    platforms = "core"
    license = "MIT"
    package_type = "static-library"

    settings = "os", "arch", "compiler", "build_type"
    options = {"fPIC": [True, False]}
    default_options = {"fPIC": True}

    exports_sources = "CMakeLists.txt", "LICENSE.txt"

    def export_sources(self):
        export_conandata_patches(self)
        copy(self, "CMakeLists.txt", self.recipe_folder, self.export_sources_folder)
        copy(self, "LICENSE.txt", self.recipe_folder, self.export_sources_folder)

    def config_options(self):
        if self.settings.os == "Windows":
            del self.options.fPIC

    def layout(self):
        cmake_layout(self, src_folder="src")

    def source(self):
        get(self, **self.conan_data["sources"][self.version], strip_root=True)
        # Upstream has no CMakeLists, so ours becomes the project file.
        copy(self, "CMakeLists.txt", self.export_sources_folder, self.source_folder)
        copy(self, "LICENSE.txt", self.export_sources_folder, self.source_folder)

    def generate(self):
        toolchain = CMakeToolchain(self)
        if self.settings.os == "Macos":
            toolchain.preprocessor_definitions["LUA_USE_MACOSX"] = ""
        elif self.settings.os in ("Linux", "Android"):
            toolchain.preprocessor_definitions["LUA_USE_LINUX"] = ""
        # iOS is left on the portable C configuration on purpose: LUA_USE_POSIX pulls in
        # the very calls the patch removes.
        toolchain.generate()

    def build(self):
        apply_conandata_patches(self)
        cmake = CMake(self)
        cmake.configure()
        cmake.build()

    def package(self):
        cmake = CMake(self)
        cmake.install()
        copy(self, "LICENSE.txt", self.source_folder,
             os.path.join(self.package_folder, "licenses"))

    def package_info(self):
        self.cpp_info.set_property("cmake_file_name", "Lua")
        self.cpp_info.libs = ["lualib"]
        if self.settings.os in ("Linux", "Android"):
            self.cpp_info.system_libs = ["m", "dl"]
