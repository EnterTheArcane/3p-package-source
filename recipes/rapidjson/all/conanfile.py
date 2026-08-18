#
# Copyright (c) Contributors to the Open 3D Engine Project.
# For complete copyright and license terms please see the LICENSE at the root of this distribution.
#
# SPDX-License-Identifier: Apache-2.0 OR MIT
#
# Adapted from the Conan Center recipe for RapidJSON (MIT). The recipe is pinned to
# the revision O3DE consumes; its build and package behavior otherwise stays native.
#

from conan import ConanFile
from conan.tools.files import copy, get
from conan.tools.layout import basic_layout

import os


required_conan_version = ">=2.1"


class RapidJsonConan(ConanFile):
    name = "rapidjson"
    version = "cci.20250205"
    description = "A fast JSON parser/generator for C++ with both SAX/DOM style APIs"
    license = "MIT"
    package_type = "header-library"
    package_id_embed_mode = "minor_mode"
    settings = "os", "arch", "compiler", "build_type"
    no_copy_source = True

    def layout(self):
        basic_layout(self, src_folder="src")

    def source(self):
        get(self, **self.conan_data["sources"][self.version], strip_root=True,
            destination=self.source_folder)

    def package(self):
        copy(self, "license.txt", self.source_folder,
             os.path.join(self.package_folder, "licenses"))
        copy(self, "*", os.path.join(self.source_folder, "include"),
             os.path.join(self.package_folder, "include"))

    def package_id(self):
        self.info.clear()

    def package_info(self):
        self.cpp_info.set_property("cmake_file_name", "RapidJSON")
        self.cpp_info.set_property("cmake_target_name", "rapidjson")
        self.cpp_info.bindirs = []
        self.cpp_info.libdirs = []
