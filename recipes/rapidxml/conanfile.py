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
    """RapidXML with the header names the engine includes.

    Upstream ships rapidxml.hpp and friends, and Conan Center packages them under those
    names. Engine code includes <rapidxml/rapidxml.h>, so the headers arrive here with a
    .h extension instead. They are vendored rather than renamed at build time because
    these are the exact headers the engine has been built against, and RapidXML has had
    no upstream release since 2009.

    Header only.
    """

    name = "rapidxml"
    version = "1.13"
    description = "Fast XML parser"
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
        self.cpp_info.bindirs = []
        self.cpp_info.libdirs = []

    def package_id(self):
        self.info.clear()
