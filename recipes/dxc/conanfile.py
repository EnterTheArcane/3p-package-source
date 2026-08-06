#
# Copyright (c) Contributors to the Open 3D Engine Project.
# For complete copyright and license terms please see the LICENSE at the root of this distribution.
#
# SPDX-License-Identifier: Apache-2.0 OR MIT
#

import os

from conan import ConanFile
from conan.tools.cmake import CMake, CMakeToolchain, cmake_layout
from conan.tools.files import apply_conandata_patches, copy, export_conandata_patches
from conan.tools.scm import Git


class DxcConan(ConanFile):
    """The DirectX Shader Compiler, from O3DE's fork.

    Only the tools ship: dxc, dxsc and the dxcompiler shared library, which the shader
    builder runs. No headers or import libraries are packaged because nothing in the
    engine links against it.

    This is an LLVM tree, so expect a long build. The source is cloned rather than
    downloaded as an archive because the build stamps in the revision.

    The version is pinned to the fork, not to upstream DXC, and that is still necessary.
    Checked against upstream v1.9.2607: of the fork's eight commits, four are cherry
    picks that have since landed upstream, but three remain O3DE-only.

      - dxsc, which rewrites DXIL to turn marked loads into specialization constants and
        emits the bit offsets so the engine can patch bytecode at runtime. Upstream has
        no equivalent. It cannot simply move into O3DE's own repository either: it
        depends on a callback the fork adds to LLVM's BitstreamWriter to observe where
        each constant is emitted, plus DXC-internal libraries no released SDK exposes.
      - Decorating a precise Position built-in as Invariant in SPIR-V output.
      - -fvk-disable-depth-hint, a workaround for mobile drivers that crash on images
        declared with unknown depth.

    Two of those are small enough to upstream. The depth hint may not even be needed any
    more: upstream maintainers note DXC now always emits a known depth, so the original
    driver crash is worth retesting before carrying the flag forward.

    Until dxsc has a home, a bump means rebasing the fork onto a newer upstream. Doing so
    would also let the four redundant cherry picks go, shrinking the delta from eight
    commits to four. Once the fork moves, only the two constants below and the C++
    standard handling in generate() need changing here.
    """

    name = "dxc"
    version = "1.8.2505.1-o3de"
    description = "DirectX Shader Compiler (O3DE fork)"
    homepage = "https://github.com/o3de/DirectXShaderCompiler"
    license = "NCSA"
    package_type = "application"

    settings = "os", "arch", "compiler", "build_type"

    _git_url = "https://github.com/o3de/DirectXShaderCompiler.git"
    _git_tag = "release-1.8.2505.1-o3de"

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
        self.cpp_info.includedirs = []
        self.cpp_info.libdirs = []
        self.cpp_info.bindirs = ["bin"]
