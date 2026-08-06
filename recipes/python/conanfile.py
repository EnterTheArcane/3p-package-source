#
# Copyright (c) Contributors to the Open 3D Engine Project.
# For complete copyright and license terms please see the LICENSE at the root of this distribution.
#
# SPDX-License-Identifier: Apache-2.0 OR MIT
#

# NOT YET VERIFIED. This recipe transposes the previous macOS build and has not been
# built end to end, so it is deliberately absent from tools/catalog.py: nothing builds
# it and CI cannot be broken by it. Add the catalog entry once a build succeeds and
# engine_check.py resolves the Python target.

import os
import shutil

from conan import ConanFile
from conan.errors import ConanInvalidConfiguration
from conan.tools.files import copy, get, patch


class PythonConan(ConanFile):
    """CPython as the engine embeds it: a relocatable framework build.

    The engine does not want a normal Python. It wants one that can be unpacked
    anywhere and still work, because it is downloaded to ~/.o3de/Python and a virtual
    environment is created from it. On macOS that means a framework whose install name
    is @rpath-relative, which is what relocatable-python rewrites it to be.

    Two patches carry over from the previous build: one teaches relocatable-python to
    reuse an already built framework and stops it hard-failing on codesigning, the
    other drops the extra third party packages python.org's installer would otherwise
    bundle. The engine installs its own requirements into the venv afterwards.

    Tcl/Tk are built from pinned source rather than taken from the machine, and expat
    is replaced with a known version, so the result does not vary with the build host.
    """

    name = "python"
    version = "3.10.13"
    description = "The Python programming language, built for embedding in O3DE"
    homepage = "https://www.python.org"
    license = "PSF-2.0"
    package_type = "shared-library"

    settings = "os", "arch", "compiler", "build_type"

    exports_sources = "patches/*"

    _tcl_tk_tag = "core-8-6-12"
    _expat_tag = "R_2_4_6"
    _relocatable_commit = "5e459c3ccea0daaf181f3b1ef2773dbefce1a563"

    def validate(self):
        if self.settings.os != "Macos":
            raise ConanInvalidConfiguration(
                "only the macOS framework build has been transposed so far; "
                "Linux builds in a container and Windows uses its own batch script"
            )

    def layout(self):
        self.folders.source = "src"
        self.folders.build = "build"

    def source(self):
        get(self, **self.conan_data["sources"][self.version], strip_root=True)

    def _prepare_third_party(self):
        """Stage the sources python.org's installer expects to find locally."""
        third_party = os.path.join(self.build_folder, "third-party")
        os.makedirs(third_party, exist_ok=True)

        # The installer looks for tcl/tk as source tarballs in one directory.
        for name in ("tcl", "tk"):
            checkout = os.path.join(self.build_folder, f"{name}8.6.12")
            self.run(
                f"git clone --branch {self._tcl_tk_tag} --depth 1 "
                f"https://github.com/tcltk/{name}.git {checkout}"
            )
            self.run(f"tar czf {os.path.join(third_party, f'{name}8.6.12-src.tar.gz')} "
                     f"-C {self.build_folder} {name}8.6.12")
        return third_party

    def _replace_expat(self):
        """Use a pinned expat rather than whatever CPython vendored."""
        expat = os.path.join(self.build_folder, "libexpat")
        self.run(f"git clone --branch {self._expat_tag} --depth 1 "
                 f"https://github.com/libexpat/libexpat.git {expat}")
        source = os.path.join(expat, "expat", "lib")
        destination = os.path.join(self.source_folder, "Modules", "expat")
        for name in os.listdir(source):
            if name.endswith((".h", ".c")):
                shutil.copy2(os.path.join(source, name), os.path.join(destination, name))

    def build(self):
        patch(self, patch_file=os.path.join(self.export_sources_folder, "patches",
                                            "open3d_python.patch"),
              base_path=self.source_folder)

        third_party = self._prepare_third_party()
        self._replace_expat()

        relocatable = os.path.join(self.build_folder, "relocatable-python")
        self.run("git clone https://github.com/gregneagle/relocatable-python.git "
                 f"{relocatable}")
        self.run(f"git -C {relocatable} reset --hard {self._relocatable_commit}")
        patch(self, patch_file=os.path.join(self.export_sources_folder, "patches",
                                            "open3d_patch.patch"),
              base_path=relocatable)

        # python.org's build script drives the whole framework build.
        architecture = "arm64" if str(self.settings.arch) == "armv8" else "x86_64"
        build_root = os.path.join(self.build_folder, "python_build")
        environment = (
            "ac_cv_header_libintl_h=no ac_cv_lib_intl_textdomain=no "
            "tcl_cv_strtod_buggy=1 ac_cv_func_strtod=yes"
        )
        self.run(
            f"{environment} python3 ./build-installer.py "
            f"--universal-archs={architecture} "
            f"--build-dir {build_root} --third-party={third_party}",
            cwd=os.path.join(self.source_folder, "Mac", "BuildScript"),
        )

        frameworks = self._frameworks
        interpreter = os.path.join(frameworks, "Python.framework", "Versions",
                                   self._short_version, "bin", f"python{self._short_version}")

        # At this point the framework still expects to live in /Library/Frameworks, so
        # the interpreter cannot load its own library from the build tree. dyld is
        # pointed at the build location for this one step; the relocation pass below is
        # what removes the absolute path for good. The previous build got away without
        # this only on machines that already had a matching Python installed system wide.
        self.run(f'DYLD_FRAMEWORK_PATH="{frameworks}" "{interpreter}" -m ensurepip')

        # Rewrite absolute paths so the framework works wherever it is unpacked.
        self.run(
            f"python3 ./make_relocatable_python_framework.py --no-unsign --upgrade-pip "
            f"--python-version {self.version} "
            f"--use-existing-framework {os.path.join(frameworks, 'Python.framework')}",
            cwd=relocatable,
        )
        self.run(
            "install_name_tool -id @rpath/Python.framework/Versions/Current/Python "
            f"{os.path.join(frameworks, 'Python.framework', 'Versions', self._short_version, 'Python')}"
        )

    @property
    def _frameworks(self):
        """Where build-installer.py stages the framework, derived rather than remembered."""
        return os.path.join(self.build_folder, "python_build", "_root", "Library", "Frameworks")

    @property
    def _short_version(self):
        return ".".join(self.version.split(".")[:2])

    def package(self):
        # shutil rather than Conan's copy: the framework is built out of symlinks, both
        # to files and to directories, and they have to arrive intact. Conan's helper
        # has no way to preserve them.
        shutil.copytree(self._frameworks, self.package_folder,
                        symlinks=True, dirs_exist_ok=True)

        licenses = os.path.join(self.package_folder, "licenses")
        copy(self, "LICENSE.txt",
             os.path.join(self.package_folder, "Python.framework", "Versions",
                          self._short_version, "lib", f"python{self._short_version}"),
             licenses)

        # Old pip wheels bundled by ensurepip are not wanted in a shipped package.
        bundled = os.path.join(self.package_folder, "Python.framework", "Versions",
                               self._short_version, "lib", f"python{self._short_version}",
                               "ensurepip", "_bundled")
        for name in os.listdir(bundled) if os.path.isdir(bundled) else []:
            if name.startswith("pip-20"):
                os.remove(os.path.join(bundled, name))

    def package_info(self):
        base = os.path.join(self.package_folder, "Python.framework", "Versions",
                            self._short_version)
        self.cpp_info.includedirs = [os.path.join(base, "Headers")]
        self.cpp_info.libdirs = [os.path.join(base, "lib")]
        self.cpp_info.bindirs = [os.path.join(base, "bin")]
