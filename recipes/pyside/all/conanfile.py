#
# Copyright (c) Contributors to the Open 3D Engine Project.
# For complete copyright and license terms please see the LICENSE at the root of this distribution.
#
# SPDX-License-Identifier: Apache-2.0 OR MIT
#

import glob
import os
import shutil
import subprocess

from conan import ConanFile
from conan.errors import ConanInvalidConfiguration
from conan.tools.files import apply_conandata_patches, copy, export_conandata_patches, get


class PySideConan(ConanFile):
    name = "pyside"
    version = "6.10.2"
    license = "LGPL-3.0"
    package_type = "shared-library"

    settings = "os", "arch", "compiler", "build_type"

    exports_sources = "pyside6.patch", "setup.py", "__init__.py"

    # Modules the engine does not use. Skipping them saves a great deal of build time
    # and avoids pulling in Qt modules that are not in our Qt package.
    _skipped_modules = ",".join([
        "Quick", "QuickControls2", "QuickTest", "QuickWidgets", "MultimediaWidgets",
        "Multimedia", "Pdf", "PdfWidgets", "Positioning", "Location", "NetworkAuth",
        "Nfc", "WebEngineQuick", "UiToolsPrivate", "RemoteObjects", "Scxml",
        "TextToSpeech", "3DCore", "3DRender", "3DInput", "3DLogic", "3DAnimation",
        "3DExtras", "AxContainer",
    ])

    def validate(self):
        if str(self.settings.os) not in ("Windows", "Linux", "Macos"):
            raise ConanInvalidConfiguration(f"pyside is not shipped for {self.settings.os}")

    def export_sources(self):
        export_conandata_patches(self)
        for name in ("pyside6.patch", "setup.py", "__init__.py"):
            copy(self, name, self.recipe_folder, self.export_sources_folder)

    def requirements(self):
        self.requires("python/3.10.13")
        self.requires("qt/6.10.2")

    def build_requirements(self):
        self.tool_requires("libclang/20.1.3")

    def layout(self):
        self.folders.source = "src"
        self.folders.build = "build"

    def source(self):
        get(self, **self.conan_data["sources"][self.version], strip_root=True)

    @property
    def _python_short_version(self):
        return "3.10"

    def _link_python_into_venv(self, python, venv):
        """Give the virtual environment the library and headers setup.py expects to find."""
        version = self._python_short_version
        if self.settings.os == "Macos":
            root = os.path.join(python, "Python.framework", "Versions", "Current")
            library = os.path.join(root, "lib", f"libpython{version}.dylib")
            libdir = os.path.join(venv, "lib", "darwin")
            linked = os.path.join(libdir, f"libpython{version}.dylib")
        else:
            root = python
            library = os.path.join(root, "lib", f"libpython{version}.so")
            libdir = os.path.join(venv, "lib", f"{self.settings.arch}-linux-gnu")
            linked = os.path.join(libdir, f"libpython{version}.so")

        os.makedirs(libdir, exist_ok=True)
        if not os.path.exists(linked):
            os.symlink(library, linked)

        headers = os.path.join(venv, "include", f"python{version}")
        if not os.path.exists(headers):
            os.makedirs(os.path.dirname(headers), exist_ok=True)
            os.symlink(os.path.join(root, "include", f"python{version}"), headers)

    def build(self):
        apply_conandata_patches(self)

        python = self.dependencies["python"].package_folder
        qt = self.dependencies["qt"].package_folder

        # setup.py wants a normal unix layout, which the macOS framework is not.
        interpreter = os.path.join(python, "Python.framework", "Versions", "Current",
                                   "bin", "python3")
        if self.settings.os != "Macos":
            interpreter = os.path.join(python, "bin", "python3")

        venv = os.path.join(self.build_folder, "venv")
        self.run(f'"{interpreter}" -m venv --system-site-packages --symlinks "{venv}"')
        venv_python = os.path.join(venv, "bin", "python3")

        # setup.py hunts for libpython and the headers in the layout a normal unix Python
        # has. A framework build has neither where it looks, so they are linked into
        # place; without this it stops with "Failed to locate the Python library".
        self._link_python_into_venv(python, venv)
        self.run(f'"{venv_python}" -m pip install --upgrade pip')
        self.run(f'"{venv_python}" -m pip install -r '
                 f'"{os.path.join(self.source_folder, "requirements.txt")}"')

        qtpaths = os.path.join(qt, "bin", "qtpaths6")
        arguments = [
            "install",
            f"--qtpaths={qtpaths}",
            "--ignore-git",
            "--parallel=8",
            "--build-type=all",
            "--skip-docs",
            "--limited-api=yes",
            f"--skip-modules={self._skipped_modules}",
        ]
        # Shiboken finds libclang through these. The libclang package declares them in
        # its buildenv, but a buildenv only reaches this command when Conan has generated
        # the environment scripts, and the packaging command line turns that off. Passed
        # explicitly here instead: otherwise shiboken picks up whatever LLVM the build
        # machine has, which is neither pinned nor the build Qt patches for it.
        libclang = self.dependencies.build["libclang"].package_folder
        environment = f'LLVM_INSTALL_DIR="{libclang}" CLANG_INSTALL_DIR="{libclang}" '

        if self.settings.os == "Macos":
            arguments += ["--macos-deployment-target=15.0", "--no-unity"]
            # Shiboken parses Qt's headers with libclang, and the libclang Qt publishes
            # is a plain LLVM build with no knowledge of Apple's SDK. Without a sysroot
            # it cannot find even <type_traits>, so the parse fails on the first Qt
            # header. Apple's own clang finds this by asking xcrun; this tells ours.
            sdk = subprocess.run(["xcrun", "--sdk", "macosx", "--show-sdk-path"],
                                 capture_output=True, text=True, check=True).stdout.strip()
            environment += f'SDKROOT="{sdk}" '

        self.run(f'{environment}"{venv_python}" setup.py {" ".join(arguments)}',
                 cwd=self.source_folder)

    def package(self):
        # setup.py names its output directory after the Python and Qt versions it found
        # and the build type, so it is discovered rather than assumed.
        candidates = glob.glob(os.path.join(self.source_folder, "build", "*", "install"))
        if not candidates:
            raise RuntimeError("setup.py produced no install directory under build/")
        install = candidates[0]

        # shutil rather than Conan's copy: the versioned dylibs are reached through
        # unversioned symlinks that the engine's config file refers to by name, and
        # Conan's helper cannot preserve them.
        for folder in ("bin", "lib", "share", "shiboken6_generator"):
            source = os.path.join(install, folder)
            if os.path.isdir(source):
                shutil.copytree(source, os.path.join(self.package_folder, folder),
                                symlinks=True, dirs_exist_ok=True)
        copy(self, "*", os.path.join(install, "PySide6", "include"),
             os.path.join(self.package_folder, "include", "PySide6"))
        copy(self, "*", os.path.join(install, "shiboken6", "include"),
             os.path.join(self.package_folder, "include", "shiboken6"))

        # Makes the shipped site-packages pip-installable, which is how the engine
        # exposes PySide to its virtual environment.
        site_packages = os.path.join(
            self.package_folder, "lib", f"python{self._python_short_version}", "site-packages")
        if self.settings.os == "Windows":
            site_packages = os.path.join(self.package_folder, "lib", "site-packages")
        for name in ("setup.py", "__init__.py"):
            copy(self, name, self.export_sources_folder, site_packages)

        copy(self, "*", os.path.join(self.source_folder, "LICENSES"),
             os.path.join(self.package_folder, "licenses"))

        # The seeded setup.py reads README.md from the package root when pip generates
        # metadata, so an editable install fails without it.
        copy(self, "README*", self.source_folder, self.package_folder)

        expected = [
            os.path.join(self.package_folder, "bin", "shiboken6"),
            os.path.join(self.package_folder, "include", "PySide6"),
            os.path.join(self.package_folder, "share", "PySide6", "typesystems"),
        ]
        missing = [os.path.relpath(p, self.package_folder) for p in expected
                   if not os.path.exists(p)]
        if missing:
            raise RuntimeError(
                f"package is incomplete, missing: {', '.join(missing)}; "
                f"setup.py installed into {install}"
            )

        if self.settings.os == "Macos":
            self._ship_libclang()
            self._fix_load_paths()

    def _ship_libclang(self):
        """Put libclang beside the tools that load it.

        shiboken6 links libclang dynamically. The previous package left that as an
        absolute path into Homebrew, so the shipped tool only ran on a machine that had
        llvm@20 installed. Shipping the library instead makes the package self contained.
        """
        source = self.dependencies.build["libclang"].package_folder
        destination = os.path.join(self.package_folder, "lib")
        os.makedirs(destination, exist_ok=True)
        for name in os.listdir(os.path.join(source, "lib")):
            if name.startswith("libclang.") and name.endswith(".dylib"):
                shutil.copy2(os.path.join(source, "lib", name),
                             os.path.join(destination, name), follow_symlinks=True)

    def _fix_load_paths(self):
        """Make the tools find their libraries relative to themselves.

        Two things have to happen. The build leaves run paths pointing into the Conan
        cache of the machine that built it, which mean nothing anywhere else, so those
        are removed. Then loader relative ones are added so the tools find the libraries
        shipped alongside them.
        """
        binaries = os.path.join(self.package_folder, "bin")
        for name in os.listdir(binaries) if os.path.isdir(binaries) else []:
            path = os.path.join(binaries, name)
            if not os.path.isfile(path) or os.path.islink(path):
                continue

            existing = subprocess.run(["otool", "-l", path], capture_output=True, text=True)
            if existing.returncode != 0 or "LC_RPATH" not in existing.stdout:
                continue  # scripts and data files sit in bin/ too

            already = {line.strip().split("path ", 1)[1].rsplit(" (offset", 1)[0]
                       for line in existing.stdout.splitlines()
                       if line.strip().startswith("path ")}

            for line in existing.stdout.splitlines():
                line = line.strip()
                if line.startswith("path ") and "/.conan2/" in line:
                    stale = line.split("path ", 1)[1].rsplit(" (offset", 1)[0]
                    self.run(f'install_name_tool -delete_rpath "{stale}" "{path}"',
                             ignore_errors=True)

            for relative in ("@loader_path/../lib", "@executable_path/../lib"):
                if relative not in already:
                    self.run(f'install_name_tool -add_rpath "{relative}" "{path}"',
                             ignore_errors=True)

    def package_info(self):
        # The curated config file describes the targets; nothing is generated from here.
        self.cpp_info.set_property("cmake_file_name", "pyside6")
        self.cpp_info.bindirs = ["bin"]
        self.cpp_info.libdirs = ["lib"]
        self.cpp_info.includedirs = ["include"]
