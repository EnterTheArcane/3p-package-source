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
from conan.tools.files import copy, get, patch


class IspcTexCompConan(ConanFile):
    name = "ispc-texcomp"
    version = "36b80aa"
    rev = 1
    platforms = "desktop"
    license = "MIT"
    package_type = "shared-library"

    settings = "os", "arch", "compiler", "build_type"

    def export_sources(self):
        # Exported by hand: the patch set is keyed by host rather than following the
        # layout export_conandata_patches expects.
        copy(self, "*.patch", os.path.join(self.recipe_folder, "patches"),
             os.path.join(self.export_sources_folder, "patches"))

    def validate(self):
        if str(self.settings.os) not in self.conan_data["ispc"]:
            raise ConanInvalidConfiguration(f"no ISPC compiler for {self.settings.os}")
        by_arch = self.conan_data["ispc"][str(self.settings.os)]
        if str(self.settings.arch) not in by_arch:
            raise ConanInvalidConfiguration(
                f"no ISPC compiler for {self.settings.os}/{self.settings.arch}")

    def layout(self):
        self.folders.source = "src"
        self.folders.build = "src"

    def source(self):
        get(self, **self.conan_data["sources"][self.version], strip_root=True)

    def _install_ispc(self):
        """Put the ISPC compiler where the project's build files expect it.

        Fetched here rather than in source() because which build it needs depends on the
        host, and source() runs once for all configurations.
        """
        ispc = self.conan_data["ispc"][str(self.settings.os)][str(self.settings.arch)]
        destination = os.path.join(self.source_folder, "ISPC", ispc["directory"])
        os.makedirs(destination, exist_ok=True)

        staging = os.path.join(self.build_folder, "ispc-download")
        get(self, url=ispc["url"], destination=staging, strip_root=True)
        for current, _dirs, files in os.walk(staging):
            for name in files:
                if name in ("ispc", "ispc.exe"):
                    target = os.path.join(destination, name)
                    shutil.copy2(os.path.join(current, name), target)
                    os.chmod(target, 0o755)
        shutil.rmtree(staging, ignore_errors=True)

    def _apply_patch(self):
        """Pick the build fixes for this host.

        Apple Silicon needs its own variant: the generic patch leaves the ISPC kernels
        targeting x86_64, which then fail to link into an arm64 library.
        """
        patches = self.conan_data["patches"][self.version]
        key = f"{self.settings.os}-{self.settings.arch}"
        patch_file = patches.get(key, patches["default"])
        patch(self, patch_file=os.path.join(self.export_sources_folder, patch_file))

    def build(self):
        self._apply_patch()
        self._install_ispc()

        if self.settings.os == "Macos":
            architecture = "arm64" if str(self.settings.arch) == "armv8" else "x86_64"
            destination = f"platform=macOS,arch={architecture}"
            self.run(
                f'xcodebuild PLATFORM_PREFERRED_ARCH={architecture} build '
                f'-scheme ispc_texcomp -project ispc_texcomp.xcodeproj '
                f'-destination "{destination}" '
                f'-derivedDataPath "{os.path.join(self.build_folder, "DerivedData")}"',
                cwd=self.source_folder,
            )
        elif self.settings.os == "Linux":
            self.run("make -f Makefile.linux", cwd=self.source_folder)
        else:
            self.run("build_windows.bat", cwd=self.source_folder)

    def package(self):
        binaries = os.path.join(self.package_folder, "bin")
        includes = os.path.join(self.package_folder, "include", "ISPC")

        copy(self, "ispc_texcomp.h", os.path.join(self.source_folder, "ispc_texcomp"),
             includes, keep_path=False)

        # Where the artefact lands depends on the build system used above.
        for root in (os.path.join(self.build_folder, "DerivedData"),
                     os.path.join(self.source_folder, "build"),
                     os.path.join(self.source_folder, "ispc_texcomp", "x64", "Release")):
            for pattern in ("*ispc_texcomp.dylib", "*ispc_texcomp.so", "ispc_texcomp.dll",
                            "ispc_texcomp.lib"):
                copy(self, pattern, root, binaries, keep_path=False)

        copy(self, "license.txt", self.source_folder,
             os.path.join(self.package_folder, "licenses"))

    def package_info(self):
        self.cpp_info.set_property("cmake_file_name", "ISPCTexComp")
        self.cpp_info.bindirs = ["bin"]
        self.cpp_info.libdirs = ["bin"]
        self.cpp_info.libs = ["ispc_texcomp"]
