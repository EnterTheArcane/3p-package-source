#
# Copyright (c) Contributors to the Open 3D Engine Project.
# For complete copyright and license terms please see the LICENSE at the root of this distribution.
#
# SPDX-License-Identifier: Apache-2.0 OR MIT
#

import os

from conan import ConanFile
from conan.errors import ConanInvalidConfiguration
from conan.tools.cmake import CMake, CMakeToolchain, cmake_layout
from conan.tools.env import Environment
from conan.tools.files import apply_conandata_patches, copy, export_conandata_patches, save
from conan.tools.scm import Git


class DxcConan(ConanFile):
    name = "dxc"
    version = "1.8.2505.1-o3de"
    license = "NCSA"
    package_type = "application"

    settings = "os", "arch", "compiler", "build_type"

    _git_url = "https://github.com/o3de/DirectXShaderCompiler.git"
    _git_tag = "release-1.8.2505.1-o3de"

    def validate(self):
        if str(self.settings.os) not in ("Windows", "Linux", "Macos"):
            raise ConanInvalidConfiguration(f"dxc is not shipped for {self.settings.os}")

    def export_sources(self):
        export_conandata_patches(self)

    def layout(self):
        cmake_layout(self, src_folder="src")

    def source(self):
        git = Git(self)
        git.clone(url=self._git_url, target=".", args=["--depth", "1", "--branch", self._git_tag])
        git.run("submodule update --init --recursive --depth 1")

    def generate(self):
        toolchain = CMakeToolchain(self)
        # This is an LLVM 3.7 fork; it picks its own C++ standard and overrides compiler
        # flags wholesale, so the repository-wide setting is dropped rather than fought
        # with. The illegal trait specialisation it used to rely on is patched out
        # instead, which is what upstream LLVM eventually did.
        toolchain.blocks.remove("cppstd")

        # The project ships a cache file that sets the HLSL-specific defaults; without it
        # the build produces a stock clang rather than a shader compiler.
        toolchain.cache_variables["CMAKE_BUILD_TYPE"] = "Release"
        toolchain.cache_variables["LLVM_APPEND_VC_REV"] = True
        toolchain.cache_variables["LLVM_DEFAULT_TARGET_TRIPLE"] = "dxil-ms-dx"
        toolchain.cache_variables["LLVM_TARGETS_TO_BUILD"] = "None"
        toolchain.cache_variables["LLVM_ENABLE_EH"] = True
        toolchain.cache_variables["LLVM_ENABLE_RTTI"] = True
        toolchain.cache_variables["LLVM_REQUIRES_EH"] = True
        toolchain.cache_variables["LLVM_REQUIRES_RTTI"] = True
        toolchain.cache_variables["LLVM_INCLUDE_DOCS"] = False
        toolchain.cache_variables["LLVM_INCLUDE_EXAMPLES"] = False
        toolchain.cache_variables["LLVM_INCLUDE_TESTS"] = False
        toolchain.cache_variables["LLVM_OPTIMIZED_TABLEGEN"] = False
        toolchain.cache_variables["LIBCLANG_BUILD_STATIC"] = True
        toolchain.cache_variables["CLANG_BUILD_EXAMPLES"] = False
        toolchain.cache_variables["CLANG_CL"] = False
        toolchain.cache_variables["CLANG_ENABLE_ARCMT"] = False
        toolchain.cache_variables["CLANG_ENABLE_STATIC_ANALYZER"] = False
        toolchain.cache_variables["CLANG_INCLUDE_TESTS"] = False
        toolchain.cache_variables["HLSL_INCLUDE_TESTS"] = False
        toolchain.cache_variables["ENABLE_SPIRV_CODEGEN"] = True
        toolchain.cache_variables["SPIRV_BUILD_TESTS"] = False
        toolchain.cache_variables["CMAKE_INSTALL_LIBDIR"] = "lib"
        toolchain.cache_variables["CMAKE_INSTALL_BINDIR"] = "bin"
        toolchain.generate()

    def build(self):
        apply_conandata_patches(self)
        cmake = CMake(self)
        cache = os.path.join(self.source_folder, "cmake", "caches", "PredefinedParams.cmake")
        environment = Environment()
        if (
            self.settings.os == "Windows"
            and self.settings.arch != self.settings_build.arch
        ):
            # LLVM's nested NATIVE build must run on the build machine. The outer
            # Conan environment deliberately selects the ARM64 MSVC tools, so give
            # that nested CMake invocation a wrapper which switches back to x64.
            wrapper = os.path.join(self.build_folder, "llvm-native-cmake.bat")
            save(
                self,
                wrapper,
                "@echo off\n"
                "call \"%VSINSTALLDIR%VC\\Auxiliary\\Build\\vcvarsall.bat\" x64 >nul\n"
                "cmake.exe %*\n",
            )
            environment.define("LLVM_NATIVE_CMAKE", wrapper)

        with environment.vars(self).apply():
            cmake.configure(cli_args=[f"-C{cache}"])
        cmake.build()

    def package(self):
        build = self.build_folder
        binaries = os.path.join(self.package_folder, "bin")
        libraries = os.path.join(self.package_folder, "lib")

        # dxc and dxsc are symlinks to versioned binaries, so the versioned names have to
        # be collected as well or the package ships links pointing at nothing.
        for pattern in ("dxc", "dxc-*", "dxsc", "dxsc-*", "dxc.exe", "dxsc.exe"):
            copy(self, pattern, os.path.join(build, "bin"), binaries, keep_path=False)
        for pattern in ("*.dll",):
            copy(self, pattern, os.path.join(build, "bin"), binaries, keep_path=False)
        for pattern in ("*dxcompiler*.dylib", "*dxcompiler*.so*", "*dxil*.dylib", "*dxil*.so*"):
            copy(self, pattern, os.path.join(build, "lib"), libraries, keep_path=False)

        copy(self, "LICENSE.TXT", self.source_folder,
             os.path.join(self.package_folder, "licenses"))

    def package_info(self):
        self.cpp_info.set_property("cmake_file_name", "DirectXShaderCompilerDxc")
        self.cpp_info.includedirs = []
        self.cpp_info.libdirs = []
        self.cpp_info.bindirs = ["bin"]
