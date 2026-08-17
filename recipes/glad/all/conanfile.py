#
# Copyright (c) Contributors to the Open 3D Engine Project.
# For complete copyright and license terms please see the LICENSE at the root of this distribution.
#
# SPDX-License-Identifier: Apache-2.0 OR MIT
#

import os

from conan import ConanFile
from conan.tools.files import copy


class GladConan(ConanFile):
    name = "glad"
    version = "2.0.0-beta"
    # The one recipe that keeps a homepage: its loaders are vendored rather than
    # downloaded, so there is no source archive for the descriptor's URL to point at.
    homepage = "https://github.com/Dav1dde/glad"
    license = "MIT"
    package_type = "header-library"
    no_copy_source = True

    exports_sources = "include/*", "LICENSE"

    def package(self):
        copy(self, "*.h", os.path.join(self.export_sources_folder, "include"),
             os.path.join(self.package_folder, "include"))
        copy(self, "LICENSE", self.export_sources_folder,
             os.path.join(self.package_folder, "licenses"))

    def package_info(self):
        self.cpp_info.set_property("cmake_file_name", "glad")
        self.cpp_info.bindirs = []
        self.cpp_info.libdirs = []

    def package_id(self):
        self.info.clear()
