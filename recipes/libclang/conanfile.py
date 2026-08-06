#
# Copyright (c) Contributors to the Open 3D Engine Project.
# For complete copyright and license terms please see the LICENSE at the root of this distribution.
#
# SPDX-License-Identifier: Apache-2.0 OR MIT
#

import os
import shutil

from conan import ConanFile
from conan.errors import ConanInvalidConfiguration
from conan.tools.files import copy, download, check_md5


# Shiboken parses Qt's headers with libclang and needs the build the Qt project itself
# uses: with plain LLVM release binaries it resolves QDirListing::IteratorFlag onto
# QDirIterator's enum and emits wrappers referencing a Default member that does not exist.
# Never shipped -- this only ever appears as a tool_requires.
#
# Needs 7z on the build machine (brew install p7zip, apt install p7zip-full, or the
# 7zip package on Windows), which is the only format Qt publishes.
class LibClangConan(ConanFile):
    name = "libclang"
    version = "20.1.3"
    license = "Apache-2.0 WITH LLVM-exception"
    package_type = "application"

    settings = "os", "arch"

    def _source(self):
        sources = self.conan_data["sources"][self.version]
        by_os = sources.get(str(self.settings.os))
        if not by_os:
            return None
        return by_os.get(str(self.settings.arch)) or by_os.get("any")

    def validate(self):
        if self._source() is None:
            raise ConanInvalidConfiguration(
                f"no prebuilt libclang for {self.settings.os}/{self.settings.arch}"
            )

    def build(self):
        source = self._source()
        archive = os.path.join(self.build_folder, "libclang.7z")
        download(self, source["url"], archive)
        check_md5(self, archive, source["md5"])

        seven_zip = shutil.which("7z") or shutil.which("7za") or shutil.which("7zz")
        if not seven_zip:
            raise ConanInvalidConfiguration(
                "7z is needed to unpack the libclang archive; install p7zip"
            )
        self.run(f'"{seven_zip}" x -y -o"{self.build_folder}" "{archive}"')

    def package(self):
        # The archives unpack to a single libclang/ directory.
        extracted = os.path.join(self.build_folder, "libclang")
        root = extracted if os.path.isdir(extracted) else self.build_folder
        for folder in ("bin", "lib", "include", "libexec", "share"):
            copy(self, "*", os.path.join(root, folder),
                 os.path.join(self.package_folder, folder))

        licenses = os.path.join(self.package_folder, "licenses")
        for name in ("LICENSE.TXT", "LICENSE", "LICENSE.txt"):
            copy(self, name, root, licenses)
        if not os.path.isdir(licenses) or not os.listdir(licenses):
            # The archives do not always carry one; record the upstream terms.
            os.makedirs(licenses, exist_ok=True)
            with open(os.path.join(licenses, "LICENSE.TXT"), "w", encoding="utf8") as handle:
                handle.write(
                    "LLVM Release License: Apache-2.0 WITH LLVM-exception\n"
                    "See https://llvm.org/LICENSE.txt\n"
                )

    def package_info(self):
        self.cpp_info.includedirs = []
        self.cpp_info.libdirs = []
        self.cpp_info.bindirs = ["bin"]
        # Shiboken looks here to find the libclang it should parse headers with.
        self.buildenv_info.define_path("CLANG_INSTALL_DIR", self.package_folder)
        self.buildenv_info.define_path("LLVM_INSTALL_DIR", self.package_folder)
