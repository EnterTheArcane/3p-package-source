#
# Copyright (c) Contributors to the Open 3D Engine Project.
# For complete copyright and license terms please see the LICENSE at the root of this distribution.
#
# SPDX-License-Identifier: Apache-2.0 OR MIT
#
# Adapted from the Conan Center recipe for Lua (MIT). O3DE adds its namespaced include
# layout and mobile sandbox patch while retaining the standard Conan package layout.
#

import os

from conan import ConanFile
from conan.errors import ConanInvalidConfiguration
from conan.tools.apple import fix_apple_shared_install_name
from conan.tools.cmake import CMake, CMakeDeps, CMakeToolchain, cmake_layout
from conan.tools.files import (apply_conandata_patches, collect_libs, copy,
                               export_conandata_patches, get, load, save)


required_conan_version = ">=2.1"


class LuaConan(ConanFile):
    name = "lua"
    version = "5.4.4"
    description = "A powerful, efficient, lightweight, embeddable scripting language"
    license = "MIT"
    package_type = "library"

    settings = "os", "arch", "compiler", "build_type"
    options = {
        "shared": [False, True],
        "fPIC": [True, False],
        "compile_as_cpp": [True, False],
        "with_tools": [True, False],
        "with_readline": [True, False],
    }
    default_options = {
        "shared": False,
        "fPIC": True,
        "compile_as_cpp": False,
        "with_tools": False,
        "with_readline": False,
    }

    def validate(self):
        if str(self.settings.os) not in ("Windows", "Linux", "Macos", "Android", "iOS"):
            raise ConanInvalidConfiguration(f"lua is not shipped for {self.settings.os}")
        if not self.options.with_tools and self.options.with_readline:
            raise ConanInvalidConfiguration(
                f"{self.ref} requires with_tools=True when with_readline=True")

    def export_sources(self):
        copy(self, "CMakeLists.txt", self.recipe_folder, self.export_sources_folder)
        export_conandata_patches(self)

    def config_options(self):
        if self.settings.os == "Windows":
            del self.options.fPIC

    def configure(self):
        if self.options.shared:
            self.options.rm_safe("fPIC")
        if not self.options.compile_as_cpp:
            self.settings.rm_safe("compiler.libcxx")
            self.settings.rm_safe("compiler.cppstd")

    def layout(self):
        cmake_layout(self, src_folder="src")

    def requirements(self):
        if self.options.with_tools and self.options.with_readline:
            self.requires("readline/8.2")

    def source(self):
        get(self, **self.conan_data["sources"][self.version], strip_root=True)

    def generate(self):
        toolchain = CMakeToolchain(self)
        toolchain.variables["LUA_SRC_DIR"] = self.source_folder.replace("\\", "/")
        toolchain.variables["COMPILE_AS_CPP"] = self.options.compile_as_cpp
        toolchain.variables["SKIP_INSTALL_TOOLS"] = not self.options.with_tools
        toolchain.variables["WITH_READLINE"] = self.options.with_readline
        toolchain.generate()
        dependencies = CMakeDeps(self)
        dependencies.generate()

    def build(self):
        apply_conandata_patches(self)
        cmake = CMake(self)
        cmake.configure(build_script_folder=os.path.join(self.source_folder, os.pardir))
        cmake.build()

    def package(self):
        # Lua's license is embedded in its public header.
        header = load(self, os.path.join(self.source_folder, "src", "lua.h"))
        license_text = header[header.find("/***", 1):header.find("****/", 1)]
        save(self, os.path.join(self.package_folder, "licenses", "COPYING.txt"),
             license_text)

        cmake = CMake(self)
        cmake.install()
        fix_apple_shared_install_name(self)

        # O3DE includes Lua as <Lua/lua.h>. Keep Conan Center's standard flat headers
        # as well so the package remains usable by conventional Conan consumers.
        copy(self, "*.h", os.path.join(self.source_folder, "src"),
             os.path.join(self.package_folder, "include", "Lua"))

    def package_info(self):
        self.cpp_info.set_property("cmake_file_name", "Lua")
        self.cpp_info.libs = collect_libs(self)
        if self.settings.os in ("Linux", "FreeBSD"):
            self.cpp_info.system_libs = ["dl", "m"]
        if self.settings.os in ("Linux", "FreeBSD", "Macos"):
            self.cpp_info.defines.extend(["LUA_USE_DLOPEN", "LUA_USE_POSIX"])
        elif self.settings.os == "Windows" and self.options.shared:
            self.cpp_info.defines.append("LUA_BUILD_AS_DLL")
