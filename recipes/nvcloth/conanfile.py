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
from conan.tools.files import apply_conandata_patches, copy, export_conandata_patches, get


class NvClothConan(ConanFile):
    """NvCloth as the engine consumes it.

    Conan Center packages NvCloth's 1.1.6 release branch. The engine cannot use it: the
    branches disagree about where the callback interfaces live, and engine code derives
    from nv::cloth::PxAssertHandler, which only exists on master. This builds the same
    master commit the previous package did.

    NvCloth also keeps the PhysX habit of building one library per configuration rather
    than one library that respects CMAKE_BUILD_TYPE, and the engine's profile build asks
    for libNvClothPROFILE. All of them ship together, so build_type does not take part
    in the package id.
    """

    name = "nvcloth"
    version = "1.1.6"
    description = "Cloth simulation library"
    homepage = "https://github.com/NVIDIAGameWorks/NvCloth"
    license = "DocumentRef-license.txt:LicenseRef-NvCloth"
    package_type = "static-library"

    settings = "os", "arch", "compiler", "build_type"

    # release last, so a failure in it is the one reported, and so the release libraries
    # are what a partial build leaves behind.
    _configurations = ("debug", "profile", "release")

    _platforms = {
        "Macos": "mac",
        "Linux": "linux",
        "Windows": "windows",
    }

    def export_sources(self):
        export_conandata_patches(self)

    def layout(self):
        self.folders.source = "src"
        self.folders.build = "build"

    def validate(self):
        if str(self.settings.os) not in self._platforms:
            raise ConanInvalidConfiguration(
                f"NvCloth has no build for {self.settings.os}; the engine only asks for "
                f"it on {', '.join(sorted(self._platforms))}"
            )

    def source(self):
        get(self, **self.conan_data["sources"][self.version], strip_root=True)

    @property
    def _compiler_dir(self):
        return os.path.join(self.source_folder, "NvCloth", "compiler", "cmake",
                            self._platforms[str(self.settings.os)])

    def build(self):
        apply_conandata_patches(self)

        # NvCloth's cmake resolves PxShared and its own source through this, the way the
        # previous build's scripts set it.
        environment = {"GW_DEPS_ROOT": self.source_folder}

        target = self._platforms[str(self.settings.os)]
        for configuration in self._configurations:
            build_dir = os.path.join(self.build_folder, configuration)
            options = [
                f'-B "{build_dir}"',
                f"-DCMAKE_BUILD_TYPE={configuration}",
                f"-DTARGET_BUILD_PLATFORM={target}",
                f'-DCMAKE_CXX_FLAGS="{self._forced_include}"',
                # No CUDA anywhere: the engine does not use GPU cloth, and it would put a
                # toolkit dependency into the build.
                "-DNV_CLOTH_ENABLE_CUDA=0",
                "-DUSE_CUDA=0",
                "-DPX_GENERATE_GPU_PROJECTS=0",
                "-DPX_STATIC_LIBRARIES=1",
                f'-DPX_OUTPUT_LIB_DIR="{build_dir}"',
                f'-DPX_OUTPUT_DLL_DIR="{build_dir}"',
                f'-DPX_OUTPUT_EXE_DIR="{build_dir}"',
            ]
            with_env = " ".join(f"{k}={v}" for k, v in environment.items())
            self.run(f'{with_env} cmake "{self._compiler_dir}" {" ".join(options)}')
            self.run(f'{with_env} cmake --build "{build_dir}"')

    @property
    def _forced_include(self):
        """<cstddef>, which NvCloth's SIMD headers need and do not include.

        They use size_t expecting it to arrive through another header, which current
        toolchains no longer let happen. It has to come from the command line: NvCloth's
        own cmake looks like it sets the compiler flags for this platform, but the
        architecture branch reads `ELSEIF()` with no condition, which is never true, so
        both branches are dead and CMAKE_CXX_FLAGS is left empty. That also means nothing
        here overwrites what we pass. The previous build had the same dead branch, so it
        was likewise built without NvCloth's intended flags.
        """
        return "/FI cstddef" if self.settings.compiler == "msvc" else "-include cstddef"

    def package(self):
        source = self.source_folder
        nvcloth = os.path.join(source, "NvCloth")

        # The layout the engine's find logic expects, kept from the previous package:
        # NvCloth's own headers, its extensions, and PxShared's headers beside them.
        copy(self, "*", os.path.join(nvcloth, "include"),
             os.path.join(self.package_folder, "NvCloth", "include"))
        copy(self, "*", os.path.join(nvcloth, "extensions", "include"),
             os.path.join(self.package_folder, "NvCloth", "extensions", "include"))
        copy(self, "*", os.path.join(source, "PxShared", "include"),
             os.path.join(self.package_folder, "PxShared", "include"))

        libraries = os.path.join(self.package_folder, "NvCloth", "lib")
        for configuration in self._configurations:
            produced = os.path.join(self.build_folder, configuration)
            for pattern in ("*.a", "*.lib"):
                copy(self, pattern, produced, libraries, keep_path=False)

        found = os.listdir(libraries) if os.path.isdir(libraries) else []
        if not found:
            raise RuntimeError(
                "no NvCloth libraries were produced; PX_OUTPUT_LIB_DIR is not where "
                "this platform's build writes them"
            )

        # Both components are licensed and both files are called license.txt, so they are
        # renamed apart rather than put in a directory each: the engine is pointed at one
        # of these as the package's LicenseFile, and that has to be a file it can read.
        licenses = os.path.join(self.package_folder, "licenses")
        os.makedirs(licenses, exist_ok=True)
        for name, folder in (("NvCloth", nvcloth), ("PxShared", os.path.join(source, "PxShared"))):
            original = os.path.join(folder, "license.txt")
            if os.path.isfile(original):
                shutil.copyfile(original, os.path.join(licenses, f"{name}-license.txt"))

    def package_id(self):
        # Every configuration ships in one package, so the requested one does not change it.
        del self.info.settings.build_type

    def package_info(self):
        # The curated config file describes the include directories, the definitions that
        # have to be defined-but-empty, and the per configuration library names.
        self.cpp_info.includedirs = [
            os.path.join("NvCloth", "include"),
            os.path.join("NvCloth", "extensions", "include"),
            os.path.join("PxShared", "include"),
        ]
        self.cpp_info.libdirs = [os.path.join("NvCloth", "lib")]
