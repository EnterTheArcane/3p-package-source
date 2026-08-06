#!/usr/bin/env python3
#
# Copyright (c) Contributors to the Open 3D Engine Project.
# For complete copyright and license terms please see the LICENSE at the root of this distribution.
#
# SPDX-License-Identifier: Apache-2.0 OR MIT
#

"""Consume built packages with the engine's own package system.

validate_package.py checks the shape of a package. This goes further and runs the
engine's cmake against it: serving the packages folder over a file:// URL, letting
ly_associate_package download and unpack them, and resolving every declared target
through find_package. Package hash and full content validation are both forced on,
so anything the engine would reject at configure time is rejected here instead.

    tools/engine_check.py packages/mac-arm --engine ../Engine
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile

# The engine's own spelling for each platform family.
PAL_NAMES = {
    "windows": "Windows",
    "linux": "Linux",
    "mac": "Mac",
    "ios": "iOS",
    "android": "Android",
    "emscripten": "Emscripten",
}

CMAKELISTS = """cmake_minimum_required(VERSION 3.22)
project(engine_check C CXX)

set(LY_ROOT_FOLDER "{engine}")
set(PAL_PLATFORM_NAME "{pal}")
set(PAL_PLATFORM_NAME_LOWERCASE "{pal_lower}")
set(LY_ARCHITECTURE_NAME_EXTENSION "")

# The engine looks up its platform package list through o3de_pal_dir. Redirecting it
# here swaps in the packages under test without touching the engine checkout.
macro(o3de_pal_dir out_var in_dir)
    set(${{out_var}} "${{CMAKE_CURRENT_SOURCE_DIR}}/pal")
endmacro()

set(LY_PACKAGE_UNPACK_LOCATION "${{CMAKE_BINARY_DIR}}/unpacked" CACHE PATH "" FORCE)
set(LY_PACKAGE_DOWNLOAD_CACHE_LOCATION "${{CMAKE_BINARY_DIR}}/cache" CACHE PATH "" FORCE)
set(LY_PACKAGE_VALIDATE_CONTENTS TRUE CACHE BOOL "" FORCE)
set(LY_PACKAGE_VALIDATE_PACKAGE TRUE CACHE BOOL "" FORCE)

include(${{LY_ROOT_FOLDER}}/cmake/3rdPartyPackages.cmake)

{resolves}

message(STATUS "ENGINE CHECK OK: {count} target(s) resolved")
"""

# Component packages such as Qt export 3rdParty::Qt::Core and never a bare 3rdParty::Qt,
# so the target cannot be required unconditionally; what must hold for every package is
# that the module reported itself found and that any library it points at exists.
RESOLVE = """ly_download_associated_package({target})
find_package({target} REQUIRED MODULE)
if (NOT {target}_FOUND)
    message(FATAL_ERROR "{target}_FOUND was not set by the package")
endif()
if (TARGET 3rdParty::{target})
    get_target_property(_loc_{safe} 3rdParty::{target} IMPORTED_LOCATION)
    if (_loc_{safe} AND NOT EXISTS "${{_loc_{safe}}}")
        message(FATAL_ERROR "3rdParty::{target}: IMPORTED_LOCATION missing ${{_loc_{safe}}}")
    endif()
endif()
"""


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("folder", help="folder holding built packages")
    parser.add_argument("--engine", default=os.environ.get("O3DE_ENGINE_PATH"),
                        help="path to the o3de engine checkout")
    parser.add_argument("--keep", action="store_true", help="keep the probe project")
    args = parser.parse_args()

    if not args.engine:
        raise SystemExit("pass --engine or set O3DE_ENGINE_PATH")
    engine = os.path.abspath(args.engine)
    if not os.path.isfile(os.path.join(engine, "cmake", "3rdPartyPackages.cmake")):
        raise SystemExit(f"not an engine checkout: {engine}")

    folder = os.path.abspath(args.folder)
    with open(os.path.join(folder, "packages-manifest.json"), encoding="utf8") as handle:
        manifest = json.load(handle)

    packages = manifest["packages"]
    if not packages:
        raise SystemExit("manifest lists no packages")

    workdir = os.path.realpath(tempfile.mkdtemp(prefix="engine-check-"))
    try:
        os.makedirs(os.path.join(workdir, "pal"))
        associations = "\n".join(
            "ly_associate_package(PACKAGE_NAME {package_name} TARGETS {targets} PACKAGE_HASH {sha256})".format(
                package_name=pkg["package_name"],
                targets=" ".join(pkg["targets"]),
                sha256=pkg["sha256"],
            )
            for pkg in packages
        )
        platform = manifest["platform"]
        # Packages ask the engine for its platform name, not ours: Qt looks up
        # Platform/Mac/Qt_mac.cmake inside itself, so "mac-arm" would not resolve.
        pal = PAL_NAMES[platform.split("-")[0]]
        pal_lower = pal.lower()
        with open(os.path.join(workdir, "pal", f"BuiltInPackages_{pal_lower}.cmake"), "w",
                  encoding="utf8") as handle:
            handle.write(associations + "\n")

        targets = [t for pkg in packages for t in pkg["targets"]]
        resolves = "\n".join(
            RESOLVE.format(target=t, safe=t.replace("::", "_").replace("-", "_")) for t in targets
        )
        with open(os.path.join(workdir, "CMakeLists.txt"), "w", encoding="utf8") as handle:
            handle.write(CMAKELISTS.format(
                engine=engine.replace("\\", "/"),
                pal=pal,
                pal_lower=pal_lower,
                resolves=resolves,
                count=len(targets),
            ))

        environment = dict(os.environ)
        environment["LY_PACKAGE_SERVER_URLS"] = "file://" + folder.replace("\\", "/")

        print(f"Resolving {len(targets)} target(s) from {len(packages)} package(s) "
              f"with the engine at {engine}")
        result = subprocess.run(
            ["cmake", "-S", workdir, "-B", os.path.join(workdir, "build")],
            env=environment, capture_output=True, text=True,
        )
        output = result.stdout + result.stderr
        if result.returncode != 0:
            print(output, file=sys.stderr)
            raise SystemExit("the engine rejected these packages")

        for line in output.splitlines():
            if "ENGINE CHECK OK" in line or "Installed And Validated" in line:
                print("  " + line.strip())
        print("\nThe engine resolved every target.")
    finally:
        if args.keep:
            print(f"probe kept at {workdir}")
        else:
            shutil.rmtree(workdir, ignore_errors=True)


if __name__ == "__main__":
    main()
