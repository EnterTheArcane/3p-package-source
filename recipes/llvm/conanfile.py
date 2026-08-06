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


class LlvmConan(ConanFile):
    """Prebuilt LLVM, used for the libclang that Shiboken parses C++ with.

    This is a build tool. It is never shipped to the engine, only ever appearing as a
    tool_requires, so nothing here reaches a package.

    The binaries are LLVM's own release artifacts rather than the libclang archives Qt
    publishes. Both work, but LLVM's are the upstream source, ship as tar.xz so no extra
    unpacking tool is needed, and carry a published sha256 rather than only an md5.

    Only the parts Shiboken needs are packaged: libclang, its C API headers, and the
    Clang builtin headers it must find while parsing. A full LLVM tree unpacks to several
    gigabytes, most of which is compilers and tooling nothing here runs.
    """

    name = "llvm"
    version = "20.1.8"
    description = "Prebuilt LLVM, for the libclang used to generate PySide bindings"
    homepage = "https://llvm.org"
    license = "Apache-2.0 WITH LLVM-exception"
    package_type = "application"

    settings = "os", "arch"

    def _source(self):
        by_os = self.conan_data["sources"][self.version].get(str(self.settings.os))
        return by_os.get(str(self.settings.arch)) if by_os else None

    def validate(self):
        if self._source() is None:
            raise ConanInvalidConfiguration(
                f"LLVM publishes no release binary for {self.settings.os}/{self.settings.arch}"
            )

    def build(self):
        get(self, **self._source(), strip_root=True)

    def package(self):
        # libclang itself, plus the import library on Windows.
        for pattern in ("libclang.*", "clang.dll", "libclang.lib"):
            for folder in ("lib", "bin"):
                copy(self, pattern, os.path.join(self.build_folder, folder),
                     os.path.join(self.package_folder, folder), keep_path=False)

        # The C API Shiboken compiles against.
        copy(self, "*", os.path.join(self.build_folder, "include", "clang-c"),
             os.path.join(self.package_folder, "include", "clang-c"))

        # Clang's builtin headers (stddef.h and friends). Parsing fails without them.
        copy(self, "*", os.path.join(self.build_folder, "lib", "clang"),
             os.path.join(self.package_folder, "lib", "clang"))

        copy(self, "LICENSE.TXT", self.build_folder,
             os.path.join(self.package_folder, "licenses"))

    def package_info(self):
        self.cpp_info.includedirs = ["include"]
        self.cpp_info.libdirs = ["lib"]
        self.cpp_info.bindirs = ["bin"]
        # Shiboken looks here to find the libclang it should parse headers with.
        self.buildenv_info.define_path("CLANG_INSTALL_DIR", self.package_folder)
        self.buildenv_info.define_path("LLVM_INSTALL_DIR", self.package_folder)
