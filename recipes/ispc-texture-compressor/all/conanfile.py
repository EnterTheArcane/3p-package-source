#
# Copyright (c) Contributors to the Open 3D Engine Project.
# For complete copyright and license terms please see the LICENSE at the root of this distribution.
#
# SPDX-License-Identifier: Apache-2.0 OR MIT
#

import os
import shutil

from conan import ConanFile
from conan.errors import ConanException, ConanInvalidConfiguration
from conan.tools.files import copy, get, patch


class IspcTextureCompressorConan(ConanFile):
    name = "ispc-texture-compressor"
    version = "36b80aa"
    license = "MIT"
    package_type = "shared-library"

    settings = "os", "arch", "compiler", "build_type"

    def build_requirements(self):
        self.tool_requires("ispc/1.31.0")

    def export_sources(self):
        # Exported by hand: the patch set is keyed by host rather than following the
        # layout export_conandata_patches expects.
        copy(self, "*.patch", os.path.join(self.recipe_folder, "patches"),
             os.path.join(self.export_sources_folder, "patches"))

    def validate(self):
        supported = {
            ("Windows", "x86_64"),
            ("Linux", "x86_64"),
            ("Macos", "armv8"),
        }
        configuration = (str(self.settings.os), str(self.settings.arch))
        if configuration not in supported:
            raise ConanInvalidConfiguration(
                f"ispc-texture-compressor is not shipped for "
                f"{self.settings.os}/{self.settings.arch}"
            )

    def layout(self):
        self.folders.source = "src"
        self.folders.build = "src"

    def source(self):
        get(self, **self.conan_data["sources"][self.version], strip_root=True)

    def _stage_ispc(self):
        """Put the tool requirement where the upstream build files expect it."""
        executable = "ispc.exe" if self.settings.os == "Windows" else "ispc"
        directory = {"Windows": "win", "Linux": "linux", "Macos": "osx"}[
            str(self.settings.os)
        ]
        source = os.path.join(
            self.dependencies.build["ispc"].package_folder, "bin", executable
        )
        if not os.path.isfile(source):
            raise ConanException(f"ispc tool requirement has no {executable}")

        destination = os.path.join(self.source_folder, "ISPC", directory)
        os.makedirs(destination, exist_ok=True)
        target = os.path.join(destination, executable)
        shutil.copy2(source, target)
        os.chmod(target, 0o755)

    def _apply_patch(self):
        """Pick the build fixes for this target."""
        patches = self.conan_data["patches"][self.version]
        patch(self, patch_file=os.path.join(self.export_sources_folder, patches["common"]))
        key = f"{self.settings.os}-{self.settings.arch}"
        patch_file = patches.get(key, patches["default"])
        patch(self, patch_file=os.path.join(self.export_sources_folder, patch_file))

    def build(self):
        self._apply_patch()
        self._stage_ispc()

        if self.settings.os == "Macos":
            architecture = "arm64" if str(self.settings.arch) == "armv8" else "x86_64"
            destination = f"platform=macOS,arch={architecture}"
            self.run(
                f'xcodebuild PLATFORM_PREFERRED_ARCH={architecture} build '
                f'-scheme ispc_texcomp -project ispc_texcomp.xcodeproj '
                f'-configuration {self.settings.build_type} '
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
        # Preserve the engine-facing target while changing the Conan reference and
        # deployment payload name.
        self.cpp_info.set_property("cmake_file_name", "ISPCTexComp")
        self.cpp_info.bindirs = ["bin"]
        self.cpp_info.libdirs = ["bin"]
        self.cpp_info.libs = ["ispc_texcomp"]
