#
# Copyright (c) Contributors to the Open 3D Engine Project.
# For complete copyright and license terms please see the LICENSE at the root of this distribution.
#
# SPDX-License-Identifier: Apache-2.0 OR MIT
#

import os

from conan import ConanFile
from conan.tools.files import copy, get


class Pybind11Conan(ConanFile):
    name = "pybind11"
    version = "2.13.6"
    rev = 1
    platforms = "desktop"

    license = "BSD-3-Clause"
    package_type = "header-library"
    no_copy_source = True

    def layout(self):
        self.folders.source = "src"

    def source(self):
        get(self, **self.conan_data["sources"][self.version], strip_root=True)

    def package(self):
        # Headers only. pybind11 also installs a set of cmake modules for building Python
        # extensions, which the engine does not use: it compiles against these headers and
        # links the Python it already has.
        copy(self, "*.h", os.path.join(self.source_folder, "include"),
             os.path.join(self.package_folder, "include"))
        copy(self, "LICENSE", self.source_folder,
             os.path.join(self.package_folder, "licenses"))

    def package_info(self):
        self.cpp_info.set_property("cmake_file_name", "pybind11")
        self.cpp_info.bindirs = []
        self.cpp_info.libdirs = []

    def package_id(self):
        self.info.clear()
