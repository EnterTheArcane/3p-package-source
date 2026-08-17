#
# Copyright (c) Contributors to the Open 3D Engine Project.
# For complete copyright and license terms please see the LICENSE at the root of this distribution.
#
# SPDX-License-Identifier: Apache-2.0 OR MIT
#
# Adapted from the Conan Center recipe for expat (MIT). Upstream's build is kept as it
# is: it already handles every platform the engine targets. What differs is the metadata
# the engine needs -- supported O3DE configurations and the name
# find_package is called with.
#

from conan import ConanFile
from conan.errors import ConanInvalidConfiguration
from conan.tools.cmake import CMake, CMakeToolchain, cmake_layout
from conan.tools.files import collect_libs, copy, get, rmdir
from conan.tools.microsoft import is_msvc, is_msvc_static_runtime
from conan.tools.scm import Version
import os

required_conan_version = ">=2"


class ExpatConan(ConanFile):
    name = "expat"
    version = "2.8.2"
    license = "MIT"
    package_type = "library"
    settings = "os", "arch", "compiler", "build_type"
    options = {
        "shared": [True, False],
        "fPIC": [True, False],
        "char_type": ["char", "wchar_t", "ushort"],
        "large_size": [True, False],
    }
    default_options = {
        "shared": False,
        "fPIC": True,
        "char_type": "char",
        "large_size": False,
    }

    def validate(self):
        if str(self.settings.os) not in ("Windows", "Linux", "Macos", "Android", "iOS"):
            raise ConanInvalidConfiguration(f"expat is not shipped for {self.settings.os}")

    def config_options(self):
        if self.settings.os == "Windows":
            del self.options.fPIC

    def configure(self):
        if self.options.shared:
            self.options.rm_safe("fPIC")
        self.settings.rm_safe("compiler.cppstd")
        self.settings.rm_safe("compiler.libcxx")

    def layout(self):
        cmake_layout(self, src_folder="src")

    def build_requirements(self):
        if Version(self.version) >= "2.7.4":
            self.tool_requires("cmake/[>=3.17]")

    def source(self):
        get(self, **self.conan_data["sources"][self.version], strip_root=True)

    def generate(self):
        tc = CMakeToolchain(self)
        tc.variables["EXPAT_BUILD_DOCS"] = False
        tc.variables["EXPAT_BUILD_EXAMPLES"] = False
        tc.variables["EXPAT_SHARED_LIBS"] = self.options.shared
        tc.variables["EXPAT_BUILD_TESTS"] = False
        tc.variables["EXPAT_BUILD_TOOLS"] = False
        tc.variables["EXPAT_CHAR_TYPE"] = self.options.char_type
        if is_msvc(self):
            tc.variables["EXPAT_MSVC_STATIC_CRT"] = is_msvc_static_runtime(self)
        tc.variables["EXPAT_BUILD_PKGCONFIG"] = False
        tc.variables["EXPAT_LARGE_SIZE"] = self.options.large_size
        tc.generate()

    def build(self):
        cmake = CMake(self)
        cmake.configure()
        cmake.build()

    def package(self):
        copy(self, "COPYING", src=self.source_folder, dst=os.path.join(self.package_folder, "licenses"))
        cmake = CMake(self)
        cmake.install()
        rmdir(self, os.path.join(self.package_folder, "lib", "pkgconfig"))
        rmdir(self, os.path.join(self.package_folder, "lib", "cmake"))
        rmdir(self, os.path.join(self.package_folder, "share"))

    def package_info(self):
        self.cpp_info.set_property("cmake_find_mode", "both")
        self.cpp_info.set_property("cmake_module_file_name", "EXPAT")
        self.cpp_info.set_property("cmake_module_target_name", "EXPAT::EXPAT")
        self.cpp_info.set_property("cmake_file_name", "expat")
        self.cpp_info.set_property("cmake_target_name", "expat::expat")
        self.cpp_info.set_property("pkg_config_name", "expat")

        self.cpp_info.libs = collect_libs(self)
        if not self.options.shared:
            self.cpp_info.defines = ["XML_STATIC"]
        if self.options.get_safe("char_type") in ("wchar_t", "ushort"):
            self.cpp_info.defines.append("XML_UNICODE")
        if self.options.get_safe("char_type") == "wchar_t":
            self.cpp_info.defines.append("XML_UNICODE_WCHAR_T")
        if self.options.large_size:
            self.cpp_info.defines.append("XML_LARGE_SIZE")

        if self.settings.os in ["Linux", "FreeBSD"]:
            self.cpp_info.system_libs.append("m")
        # The name the engine calls find_package with.
        self.cpp_info.set_property("cmake_file_name", "expat")
