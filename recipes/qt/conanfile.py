#
# Copyright (c) Contributors to the Open 3D Engine Project.
# For complete copyright and license terms please see the LICENSE at the root of this distribution.
#
# SPDX-License-Identifier: Apache-2.0 OR MIT
#

# NOT YET VERIFIED. This recipe transposes the previous Qt build and has not been built
# end to end, so it is deliberately absent from tools/catalog.py: nothing builds it and
# CI cannot be broken by it. Add the catalog entry once a build succeeds and
# engine_check.py resolves the Qt target.

import os

from conan import ConanFile
from conan.tools.files import apply_conandata_patches, copy, export_conandata_patches, get


class QtConan(ConanFile):
    """Qt, restricted to the modules the engine actually uses.

    Conan Center has a Qt recipe, but it does not have 6.10.2 and it packages Qt
    differently from what the engine's FindQt expects: a relocatable lib/cmake/Qt6 tree,
    host tools in both bin and libexec, plugins, and translations. Driving Qt's own
    configure script the way the previous build did is closer to the result the engine
    needs than bending the Conan Center recipe into that shape.

    Only qtbase, qtimageformats, qtsvg, qttranslations and qttools are built. zlib and
    tiff are taken from Qt's bundled copies rather than ours: the engine consumes Qt as
    a self-contained unit, and mixing the two sets of symbols has caused problems before.

    The curated cmake in cmake/ replaces the generated config wholesale. It is the file
    that defines ly_qt_moc_target and friends, which the engine calls for every target
    with AUTOMOC, so it has to exist before the first such target is declared.
    """

    name = "qt"
    version = "6.10.2"
    description = "Qt, the cross platform application framework"
    homepage = "https://www.qt.io/"
    license = "LGPL-3.0"
    package_type = "shared-library"

    settings = "os", "arch", "compiler", "build_type"

    exports_sources = "recursion-check.patch"

    _modules = "qtbase,qtimageformats,qtsvg,qttranslations,qttools"

    def export_sources(self):
        export_conandata_patches(self)
        copy(self, "recursion-check.patch", self.recipe_folder, self.export_sources_folder)

    def requirements(self):
        # macOS uses Secure Transport; the others link OpenSSL for Qt Network.
        if self.settings.os in ("Linux", "Windows"):
            self.requires("openssl/3.6.3")

    def layout(self):
        self.folders.source = "src"
        self.folders.build = "build"

    def source(self):
        get(self, **self.conan_data["sources"][self.version], strip_root=True)

    def build(self):
        apply_conandata_patches(self)

        prefix = self.package_folder
        options = [
            f"-prefix {prefix}",
            f"-submodules {self._modules}",
            "-nomake examples",
            "-nomake tests",
            "-release",
            "-c++std c++20",
            "-opensource",
            "-confirm-license",
            "-no-icu",
            "-qt-tiff",
            "-qt-zlib",
        ]
        if self.settings.os == "Macos":
            options += ["-platform macx-clang", "-dbus-linked", "-framework"]
        elif self.settings.os == "Linux":
            options += ["-platform linux-clang", "-xcb"]
        else:
            options += ["-platform win32-msvc", "-opengl dynamic", "-openssl-linked"]

        configure = os.path.join(self.source_folder, "configure")
        self.run(f"{configure} {' '.join(options)}", cwd=self.build_folder)
        self.run("cmake --build . --parallel", cwd=self.build_folder)

    def package(self):
        self.run("cmake --install . --config Release", cwd=self.build_folder)

        if self.settings.os == "Macos":
            self._link_framework_headers()

        copy(self, "LGPL-3.0-only.txt", os.path.join(self.source_folder, "LICENSES"),
             os.path.join(self.package_folder, "licenses"))

    def _link_framework_headers(self):
        """Give the framework build a flat include tree.

        Installing Qt as macOS frameworks leaves include/ empty, because the headers
        live inside each framework. Consumers still write #include <QtCore/...>, so each
        framework's Headers directory is linked back into include/.
        """
        include = os.path.join(self.package_folder, "include")
        libraries = os.path.join(self.package_folder, "lib")
        os.makedirs(include, exist_ok=True)
        for entry in sorted(os.listdir(libraries)) if os.path.isdir(libraries) else []:
            if not entry.endswith(".framework"):
                continue
            module = entry[: -len(".framework")]
            target = os.path.join(include, module)
            if not os.path.exists(target):
                os.symlink(os.path.join("..", "lib", entry, "Headers"), target)

    def package_info(self):
        # The curated config file describes the targets; nothing is generated from here.
        self.cpp_info.bindirs = ["bin", "libexec"]
        self.cpp_info.libdirs = ["lib"]
        self.cpp_info.includedirs = ["include"]
