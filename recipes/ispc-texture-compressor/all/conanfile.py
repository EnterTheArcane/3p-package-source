#
# Copyright (c) Contributors to the Open 3D Engine Project.
# For complete copyright and license terms please see the LICENSE at the root of this distribution.
#
# SPDX-License-Identifier: Apache-2.0 OR MIT
#

import os

from conan import ConanFile
from conan.errors import ConanException, ConanInvalidConfiguration
from conan.tools.cmake import CMake, CMakeToolchain, cmake_layout
from conan.tools.files import apply_conandata_patches, copy, export_conandata_patches, get


class IspcTextureCompressorConan(ConanFile):
    name = "ispc-texture-compressor"
    version = "36b80aa"
    license = "MIT"
    package_type = "shared-library"

    settings = "os", "arch", "compiler", "build_type"

    exports_sources = "CMakeLists.txt"

    def build_requirements(self):
        self.tool_requires("ispc/1.31.0")

    def export_sources(self):
        export_conandata_patches(self)
        copy(self, "CMakeLists.txt", self.recipe_folder, self.export_sources_folder)

    def validate(self):
        supported = {
            ("Windows", "x86_64"),
            ("Linux", "x86_64"),
            ("Macos", "armv8"),
        }
        configuration = (str(self.settings.os), str(self.settings.arch))
        if configuration not in supported:
            raise ConanInvalidConfiguration(
                f"ispc-texture-compressor is not shipped for "
                f"{self.settings.os}/{self.settings.arch}"
            )

    def layout(self):
        cmake_layout(self, src_folder="src")

    def source(self):
        get(self, **self.conan_data["sources"][self.version], strip_root=True)
        copy(self, "CMakeLists.txt", self.export_sources_folder, self.source_folder)

    def generate(self):
        dependency = self.dependencies.build["ispc"]
        executable = "ispc.exe" if self.settings_build.os == "Windows" else "ispc"
        compiler = os.path.join(dependency.package_folder, "bin", executable)
        if not os.path.isfile(compiler):
            raise ConanException(f"ispc tool requirement has no {executable}")

        toolchain = CMakeToolchain(self)
        toolchain.cache_variables["BUILD_SHARED_LIBS"] = True
        toolchain.cache_variables["CMAKE_ISPC_COMPILER"] = compiler.replace("\\", "/")
        toolchain.generate()

    def build(self):
        apply_conandata_patches(self)
        cmake = CMake(self)
        cmake.configure()
        cmake.build()

    def package(self):
        cmake = CMake(self)
        cmake.install()
        copy(self, "license.txt", self.source_folder,
             os.path.join(self.package_folder, "licenses"))

    def package_info(self):
        # Preserve the engine-facing target while changing the Conan reference and
        # deployment payload name.
        self.cpp_info.set_property("cmake_file_name", "ISPCTexComp")
        self.cpp_info.libs = ["ispc_texcomp"]
