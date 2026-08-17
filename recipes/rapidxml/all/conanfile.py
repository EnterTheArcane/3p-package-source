#
# Copyright (c) Contributors to the Open 3D Engine Project.
# For complete copyright and license terms please see the LICENSE at the root of this distribution.
#
# SPDX-License-Identifier: Apache-2.0 OR MIT
#

import os

from conan import ConanFile
from conan.tools.files import copy


class RapidXmlConan(ConanFile):
    name = "rapidxml"
    version = "1.13"
    # Kept, like glad's: these headers are vendored rather than downloaded, so there is
    # no source archive for the descriptor's URL to point at.
    homepage = "https://rapidxml.sourceforge.net"
    license = "BSL-1.0 OR MIT"
    package_type = "header-library"
    no_copy_source = True

    exports_sources = "include/*", "license.txt"

    def package(self):
        copy(self, "*.h", os.path.join(self.export_sources_folder, "include"),
             os.path.join(self.package_folder, "include"))
        copy(self, "license.txt", self.export_sources_folder,
             os.path.join(self.package_folder, "licenses"))

    def package_info(self):
        self.cpp_info.set_property("cmake_file_name", "RapidXML")
        self.cpp_info.bindirs = []
        self.cpp_info.libdirs = []

    def package_id(self):
        self.info.clear()
