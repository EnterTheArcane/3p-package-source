#
# Copyright (c) Contributors to the Open 3D Engine Project.
# For complete copyright and license terms please see the LICENSE at the root of this distribution.
#
# SPDX-License-Identifier: Apache-2.0 OR MIT
#
# Adapted from the Conan Center recipe for xxHash (MIT). O3DE only adds compatibility
# headers under include/xxhash and keeps the engine-facing CMake package name lowercase.
#

import os

from conan import ConanFile
from conan.errors import ConanInvalidConfiguration
from conan.tools.cmake import CMake, CMakeToolchain, cmake_layout
from conan.tools.files import (apply_conandata_patches, copy,
                               export_conandata_patches, get, rmdir)


required_conan_version = ">=2.1"


class XxHashConan(ConanFile):
    name = "xxhash"
    version = "0.8.3"
    description = "Extremely fast non-cryptographic hash algorithm"
    license = "BSD-2-Clause"
    package_type = "library"
    settings = "os", "arch", "compiler", "build_type"
    options = {
        "shared": [True, False],
        "fPIC": [True, False],
        "utility": [True, False],
    }
    default_options = {
        "shared": False,
        "fPIC": True,
        "utility": False,
    }

    def export_sources(self):
        export_conandata_patches(self)

    def config_options(self):
        if self.settings.os == "Windows":
            del self.options.fPIC

    def configure(self):
        if self.options.shared:
            self.options.rm_safe("fPIC")
        self.settings.rm_safe("compiler.cppstd")
        self.settings.rm_safe("compiler.libcxx")

    def validate(self):
        if str(self.settings.os) not in ("Windows", "Linux", "Macos"):
            raise ConanInvalidConfiguration(f"xxhash is not shipped for {self.settings.os}")

    def layout(self):
        cmake_layout(self, src_folder="src")

    def source(self):
        get(self, **self.conan_data["sources"][self.version], strip_root=True)

    def generate(self):
        toolchain = CMakeToolchain(self)
        toolchain.variables["XXHASH_BUNDLED_MODE"] = False
        toolchain.variables["XXHASH_BUILD_XXHSUM"] = self.options.utility
        toolchain.cache_variables["CMAKE_MACOSX_BUNDLE"] = False
        toolchain.cache_variables["CMAKE_POLICY_DEFAULT_CMP0042"] = "NEW"
        toolchain.generate()

    def build(self):
        apply_conandata_patches(self)
        cmake = CMake(self)
        cmake.configure(build_script_folder=os.path.join(
            self.source_folder, "cmake_unofficial"))
        cmake.build()

    def package(self):
        copy(self, "LICENSE", self.source_folder,
             os.path.join(self.package_folder, "licenses"))
        cmake = CMake(self)
        cmake.install()
        rmdir(self, os.path.join(self.package_folder, "lib", "cmake"))
        rmdir(self, os.path.join(self.package_folder, "lib", "pkgconfig"))
        rmdir(self, os.path.join(self.package_folder, "share"))

        # O3DE includes xxHash as <xxhash/xxhash.h>. Preserve Conan Center's flat
        # headers too so standard consumers can continue to use <xxhash.h>.
        include = os.path.join(self.package_folder, "include", "xxhash")
        copy(self, "xxhash.h", self.source_folder, include)
        copy(self, "xxh3.h", self.source_folder, include)

    def package_info(self):
        self.cpp_info.set_property("cmake_file_name", "xxhash")
        self.cpp_info.set_property("cmake_target_name", "xxHash::xxhash")
        self.cpp_info.set_property("pkg_config_name", "libxxhash")
        self.cpp_info.components["libxxhash"].libs = ["xxhash"]
        self.cpp_info.components["libxxhash"].set_property(
            "cmake_target_name", "xxHash::xxhash")
        # XXH_INLINE_ALL is deliberately not defined here. Engine code defines it itself,
        # inside a namespace, to keep xxHash's symbols out of the rest of the module.
        # Defining it for every consumer would both defeat that and, under -Werror,
        # break the build on the redefinition.
