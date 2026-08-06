#
# Copyright (c) Contributors to the Open 3D Engine Project.
# For complete copyright and license terms please see the LICENSE at the root of this distribution.
#
# SPDX-License-Identifier: Apache-2.0 OR MIT
#

# NOT YET VERIFIED. This recipe transposes the previous PhysX 5 build and has not been
# built end to end, so it is deliberately absent from tools/catalog.py: nothing builds
# it and CI cannot be broken by it. Add the catalog entry once a build succeeds and
# engine_check.py resolves the PhysX5 target.

import os
import shutil

from conan import ConanFile
from conan.tools.files import (
    apply_conandata_patches, copy, export_conandata_patches, get, replace_in_file,
)


class PhysXConan(ConanFile):
    """NVIDIA PhysX 5, built in all four of the configurations the engine selects between.

    PhysX is unusual here: the engine picks between release, profile, checked and debug
    libraries at consume time, so all four are built and packaged side by side under
    bin/static/<config>. That is why build_type is removed from the package id; one
    package answers for every configuration.

    PhysX 4 is not built. It is deprecated and the engine's PhysX5 gem is what consumes
    this package.

    Upstream drives its build through generate_projects plus preset xml files rather
    than plain CMake, and fetches its own dependencies with packman, so this shells out
    to those scripts instead of using the CMake helpers.
    """

    name = "physx"
    version = "5.1.1"
    description = "NVIDIA PhysX SDK"
    homepage = "https://github.com/NVIDIA-Omniverse/PhysX"
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

    def build(self):
        apply_conandata_patches(self)
        self._relax_warnings()

        physx = os.path.join(self.source_folder, "physx")
        preset, _ = self._preset

        # packman fetches the toolchain bits PhysX expects to find beside the source.
        packman = os.path.join(physx, "buildtools", "packman",
                               "packman.cmd" if self.settings.os == "Windows" else "packman")
        self.run(f'"{packman}" update -y', cwd=physx)

        generate = "generate_projects.bat" if self.settings.os == "Windows" else "./generate_projects.sh"
        self.run(f"{generate} {preset}", cwd=physx)

        for configuration in self._configurations:
            build_dir = os.path.join(physx, "compiler", preset)
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
        self.cpp_info.includedirs = ["physx/include"]
        self.cpp_info.libdirs = ["physx/bin/static/release"]
