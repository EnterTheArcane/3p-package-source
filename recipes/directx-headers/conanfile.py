#
# Copyright (c) Contributors to the Open 3D Engine Project.
# For complete copyright and license terms please see the LICENSE at the root of this distribution.
#
# SPDX-License-Identifier: Apache-2.0 OR MIT
#
# Adapted from the Conan Center recipe for directx-headers (MIT). Upstream's build is kept as it
# is: it already handles every platform the engine targets. What differs is the metadata
# the engine needs -- the release counter, the platforms we ship it for, and the name
# find_package is called with.
#

from conan import ConanFile
from conan.errors import ConanInvalidConfiguration
from conan.tools.build import check_min_cppstd
from conan.tools.env import VirtualBuildEnv
from conan.tools.files import copy, get, rmdir
from conan.tools.layout import basic_layout
from conan.tools.meson import Meson, MesonToolchain
import os


required_conan_version = ">=2.1"


class DirectXHeadersConan(ConanFile):
    name = "directx-headers"
    version = "1.619.1"
    rev = 1
    platforms = 'windows'
    license = "MIT"
    package_type = "static-library"
    settings = "os", "arch", "compiler", "build_type"

    def layout(self):
        basic_layout(self, src_folder="src")

    def validate(self):
        if self.settings.os not in ("Linux", "Windows"):
            raise ConanInvalidConfiguration(f"{self.name} is not supported on {self.settings.os}")
        check_min_cppstd(self, 11)

    def build_requirements(self):
        self.tool_requires("meson/[>=1.2.2 <2]")

    def source(self):
        get(self, **self.conan_data["sources"][self.version], strip_root=True)

    def generate(self):
        tc = MesonToolchain(self)
        tc.project_options["build-test"] = False
        tc.generate()
        virtual_build_env = VirtualBuildEnv(self)
        virtual_build_env.generate()

    def build(self):
        meson = Meson(self)
        meson.configure()
        meson.build()

    def package(self):
        copy(self, "LICENSE", self.source_folder, os.path.join(self.package_folder, "licenses"))
        meson = Meson(self)
        meson.install()
        rmdir(self, os.path.join(self.package_folder, "lib", "pkgconfig"))

    def package_info(self):
        if self.settings.os == "Linux" or self.settings.get_safe("os.subsystem") == "wsl":
            self.cpp_info.includedirs.append(os.path.join("include", "wsl", "stubs"))
        self.cpp_info.libs = ["d3dx12-format-properties", "DirectX-Guids"]
        self.cpp_info.set_property("cmake_file_name", "DirectX-Headers")
        self.cpp_info.set_property("cmake_target_name", "Microsoft::DirectX-Headers")
        self.cpp_info.set_property("pkg_config_name", "DirectX-Headers")
        if self.settings.os == "Windows":
            self.cpp_info.system_libs.append("d3d12")
        if self.settings.compiler == "msvc":
            self.cpp_info.system_libs.append("dxcore")
        # The name the engine calls find_package with.
        self.cpp_info.set_property("cmake_file_name", "d3dx12")
