#
# Copyright (c) Contributors to the Open 3D Engine Project.
# For complete copyright and license terms please see the LICENSE at the root of this distribution.
#
# SPDX-License-Identifier: Apache-2.0 OR MIT
#

# This recipe transposes the previous PhysX 5 build. Its supported configurations are
# enforced by validate(); engine_check.py remains the end-to-end package proof.

import os
import shutil

from conan import ConanFile
from conan.errors import ConanInvalidConfiguration
from conan.tools.files import (
    apply_conandata_patches, copy, export_conandata_patches, get, replace_in_file,
)


class PhysXConan(ConanFile):
    name = "physx"
    version = "5.1.1"
    license = "BSD-3-Clause"
    package_type = "static-library"

    settings = "os", "arch", "compiler", "build_type"

    _configurations = ("release", "profile", "checked", "debug")

    # Preset to build with, and the directory the libraries actually land in. The two
    # are not the same, and the second is not always named after the target: an arm64
    # macOS build writes into bin/mac.x86_64. The name is simply wrong upstream, so it
    # is recorded here rather than derived.
    _presets = {
        ("Windows", "x86_64"): ("vc16win64", "win.x86_64.vc142.md"),
        ("Linux", "x86_64"): ("linux", "linux.clang"),
        ("Linux", "armv8"): ("linux-aarch64", "linux.aarch64"),
        ("Macos", "x86_64"): ("mac64", "mac.x86_64"),
        ("Macos", "armv8"): ("mac-arm64", "mac.x86_64"),
        ("iOS", "armv8"): ("ios64", "ios.arm_64"),
        ("Android", "armv8"): ("android-arm64-v8a", "android.arm64-v8a"),
    }

    def validate(self):
        key = (str(self.settings.os), str(self.settings.arch))
        if key not in self._presets:
            raise ConanInvalidConfiguration(
                f"physx is not shipped for {self.settings.os}/{self.settings.arch}"
            )

    def export_sources(self):
        export_conandata_patches(self)

    def layout(self):
        self.folders.source = "src"
        self.folders.build = "src"

    def source(self):
        get(self, **self.conan_data["sources"][self.version], strip_root=True)

    @property
    def _preset(self):
        key = (str(self.settings.os), str(self.settings.arch))
        if key not in self._presets:
            raise RuntimeError(f"no PhysX preset for {key}")
        return self._presets[key]

    def _relax_warnings(self):
        """Stop new compiler warnings from failing this build.

        PhysX compiles with -Weverything -Werror and a long list of suppressions written
        against the compilers of the day. Every toolchain release since has added
        warnings that list does not mention, and each one fails the build: first
        -Wmissing-include-dirs, then -Wswitch-default, and so on.

        Suppressing them one at a time means rediscovering the next one on every compiler
        upgrade, so -Werror is switched off instead. We are packaging a pinned upstream
        release, not developing PhysX; its warnings are not ours to act on. -Wno-error
        goes at the end of the flag list so it wins regardless of what precedes it.
        """
        additions = "-Wno-error -Wno-missing-include-dirs -Wno-poison-system-directories -gdwarf-2"
        for platform in ("mac", "ios", "linux", "android"):
            path = os.path.join(self.source_folder, "physx", "source", "compiler",
                                "cmake", platform, "CMakeLists.txt")
            if os.path.isfile(path):
                replace_in_file(self, path, "-gdwarf-2", additions, strict=False)

    def _prepare_preset(self):
        """Keep the generated SDK limited to the static libraries O3DE consumes."""
        preset, _ = self._preset
        path = os.path.join(
            self.source_folder, "physx", "buildtools", "presets", "public",
            f"{preset}.xml",
        )
        replace_in_file(
            self, path,
            'name="PX_BUILDSNIPPETS" value="True"',
            'name="PX_BUILDSNIPPETS" value="False"',
            strict=False,
        )
        replace_in_file(
            self, path,
            'name="PX_BUILDPVDRUNTIME" value="True"',
            'name="PX_BUILDPVDRUNTIME" value="False"',
            strict=False,
        )
        replace_in_file(
            self, path,
            'name="PX_GENERATE_STATIC_LIBRARIES" value="False"',
            'name="PX_GENERATE_STATIC_LIBRARIES" value="True"',
            strict=False,
        )
        if self.settings.os == "Windows":
            # Match O3DE's dynamic MSVC runtime profile for every library flavor.
            replace_in_file(
                self, path,
                'name="NV_USE_STATIC_WINCRT" value="True"',
                'name="NV_USE_STATIC_WINCRT" value="False"',
                strict=False,
            )
            replace_in_file(
                self, path,
                'name="NV_USE_DEBUG_WINCRT" value="True"',
                'name="NV_USE_DEBUG_WINCRT" value="False"',
                strict=False,
            )

    def build(self):
        apply_conandata_patches(self)
        self._relax_warnings()
        self._prepare_preset()

        physx = os.path.join(self.source_folder, "physx")
        preset, _ = self._preset

        # generate_projects initializes packman and pulls the pinned dependencies.
        # Running `packman update` first mutates the vendored launcher and the current
        # packman release returns to the old Windows batch file as a command named `*`.
        generate = "generate_projects.bat" if self.settings.os == "Windows" else "./generate_projects.sh"
        self.run(f"{generate} {preset}", cwd=physx)

        for configuration in self._configurations:
            # Linux presets are single-config and generation creates one build tree per
            # flavor; Visual Studio and Xcode use a single multi-config tree.
            directory = (
                f"{preset}-{configuration}"
                if self.settings.os == "Linux"
                else preset
            )
            build_dir = os.path.join(physx, "compiler", directory)
            self.run(f'cmake --build "{build_dir}" --config {configuration}', cwd=physx)

    def package(self):
        physx = os.path.join(self.source_folder, "physx")
        _, output = self._preset
        destination = os.path.join(self.package_folder, "physx")

        # Headers come from the source tree rather than an install step: only the release
        # configuration installs, and the headers are identical across configurations.
        copy(self, "*", os.path.join(physx, "include"),
             os.path.join(destination, "include"))
        copy(self, "*", os.path.join(physx, "source", "fastxml"),
             os.path.join(destination, "source", "fastxml"))

        # Each configuration keeps its own libraries; the config file maps the engine's
        # build types onto these directories.
        found = 0
        for configuration in self._configurations:
            produced = os.path.join(physx, "bin", output, configuration)
            target = os.path.join(destination, "bin", "static", configuration)
            for pattern in ("*.a", "*.lib"):
                copy(self, pattern, produced, target, keep_path=False)
            found += len(os.listdir(target)) if os.path.isdir(target) else 0

        if not found:
            raise RuntimeError(
                f"no PhysX libraries found under physx/bin/{output}; "
                "the output directory for this platform is wrong"
            )

        for name in ("README.md", "version.txt"):
            copy(self, name, physx, destination)
        copy(self, "LICENSE.md", self.source_folder,
             os.path.join(self.package_folder, "licenses"))

    def package_id(self):
        # One package carries every configuration, so the requested one does not change it.
        del self.info.settings.build_type

    def package_info(self):
        # The curated config file describes the targets and their configuration mapping.
        self.cpp_info.set_property("cmake_file_name", "PhysX5")
        self.cpp_info.includedirs = ["physx/include"]
        self.cpp_info.libdirs = ["physx/bin/static/release"]
