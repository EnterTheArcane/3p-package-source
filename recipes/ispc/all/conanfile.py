#
# Copyright (c) Contributors to the Open 3D Engine Project.
# For complete copyright and license terms please see the LICENSE at the root of this distribution.
#
# SPDX-License-Identifier: Apache-2.0 OR MIT
#

import os

from conan import ConanFile
from conan.errors import ConanInvalidConfiguration
from conan.tools.files import copy, get
from conan.tools.layout import basic_layout


class IspcConan(ConanFile):
    name = "ispc"
    version = "1.31.0"
    license = "BSD-3-Clause"
    package_type = "application"
    upload_policy = "skip"

    settings = "os", "arch"

    def validate(self):
        sources = self.conan_data["sources"][self.version]
        by_arch = sources.get(str(self.settings.os), {})
        if str(self.settings.arch) not in by_arch:
            raise ConanInvalidConfiguration(
                f"no ISPC compiler for {self.settings.os}/{self.settings.arch}"
            )

    def layout(self):
        basic_layout(self)

    def build(self):
        sources = self.conan_data["sources"][self.version]
        archive = sources[str(self.settings.os)][str(self.settings.arch)]
        get(self, **archive, destination=self.build_folder, strip_root=True)

    def package(self):
        copy(self, "*", self.build_folder, self.package_folder)

    def package_info(self):
        binaries = os.path.join(self.package_folder, "bin")
        self.cpp_info.set_property("cmake_file_name", "ISPC")
        self.cpp_info.includedirs = []
        self.cpp_info.libdirs = []
        self.cpp_info.bindirs = ["bin"]
        self.buildenv_info.prepend_path("PATH", binaries)
        self.runenv_info.prepend_path("PATH", binaries)
