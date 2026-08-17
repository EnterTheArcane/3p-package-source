#
# Copyright (c) Contributors to the Open 3D Engine Project.
# For complete copyright and license terms please see the LICENSE at the root of this distribution.
#
# SPDX-License-Identifier: Apache-2.0 OR MIT
#

from conan import ConanFile
from conan.errors import ConanInvalidConfiguration
from conan.tools.files import copy, get
import os


class XxHashConan(ConanFile):
    name = "xxhash"
    version = "0.8.3"
    license = "BSD-2-Clause"
    package_type = "header-library"
    settings = "os", "arch", "compiler", "build_type"
    no_copy_source = True

    def validate(self):
        if str(self.settings.os) not in ("Windows", "Linux", "Macos"):
            raise ConanInvalidConfiguration(f"xxhash is not shipped for {self.settings.os}")

    def layout(self):
        self.folders.source = "src"

    def source(self):
        get(self, **self.conan_data["sources"][self.version], strip_root=True)

    def package(self):
        include = os.path.join(self.package_folder, "include", "xxhash")
        copy(self, "xxhash.h", self.source_folder, include)
        copy(self, "xxh3.h", self.source_folder, include)
        copy(self, "LICENSE", self.source_folder,
             os.path.join(self.package_folder, "licenses"))

    def package_info(self):
        self.cpp_info.set_property("cmake_file_name", "xxhash")
        self.cpp_info.bindirs = []
        self.cpp_info.libdirs = []
        # XXH_INLINE_ALL is deliberately not defined here. Engine code defines it itself,
        # inside a namespace, to keep xxHash's symbols out of the rest of the module.
        # Defining it for every consumer would both defeat that and, under -Werror,
        # break the build on the redefinition.

    def package_id(self):
        self.info.clear()
