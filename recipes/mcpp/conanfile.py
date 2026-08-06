#
# Copyright (c) Contributors to the Open 3D Engine Project.
# For complete copyright and license terms please see the LICENSE at the root of this distribution.
#
# SPDX-License-Identifier: Apache-2.0 OR MIT
#

import os

from conan import ConanFile
from conan.tools.files import apply_conandata_patches, copy, export_conandata_patches, get
from conan.tools.gnu import Autotools, AutotoolsToolchain
from conan.tools.layout import basic_layout


class McppConan(ConanFile):
    name = "mcpp"
    version = "2.7.2_az.2"
    rev = 1
    platforms = "desktop"
    license = "BSD-2-Clause"
    package_type = "static-library"

    settings = "os", "arch", "compiler", "build_type"
    options = {"fPIC": [True, False]}
    default_options = {"fPIC": True}

    def export_sources(self):
        export_conandata_patches(self)

    def config_options(self):
        if self.settings.os == "Windows":
            del self.options.fPIC

    def layout(self):
        basic_layout(self, src_folder="src")

    def source(self):
        # The version here carries the fork suffix; the tarball does not.
        get(self, **self.conan_data["sources"]["2.7.2"], strip_root=True)

    def generate(self):
        toolchain = AutotoolsToolchain(self)
        toolchain.configure_args += ["--enable-mcpplib", "--disable-shared", "--enable-static"]
        if self.settings.os in ("Macos", "iOS"):
            # 2.7.2 predates C99 declarations being mandatory; recent clang errors on them.
            toolchain.extra_cflags.append("-Wno-implicit-function-declaration")
        toolchain.generate()

    def build(self):
        apply_conandata_patches(self)
        autotools = Autotools(self)
        autotools.configure()
        autotools.make()

    def package(self):
        autotools = Autotools(self)
        autotools.install()

        copy(self, "LICENSE", self.source_folder,
             os.path.join(self.package_folder, "licenses"))

        # Autotools leaves libtool archives and, with --enable-mcpplib, a driver binary
        # that nothing here consumes.
        for folder in ("lib", "bin"):
            path = os.path.join(self.package_folder, folder)
            for name in os.listdir(path) if os.path.isdir(path) else []:
                if name.endswith(".la"):
                    os.remove(os.path.join(path, name))

    def package_info(self):
        self.cpp_info.set_property("cmake_file_name", "mcpp")
        self.cpp_info.libs = ["mcpp"]
