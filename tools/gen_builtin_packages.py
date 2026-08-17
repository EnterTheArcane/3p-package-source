#!/usr/bin/env python3
#
# Copyright (c) Contributors to the Open 3D Engine Project.
# For complete copyright and license terms please see the LICENSE at the root of this distribution.
#
# SPDX-License-Identifier: Apache-2.0 OR MIT
#

"""Update the engine's package pins from a set of built packages.

Most pins live in cmake/3rdParty/Platform/<Platform>/BuiltInPackages_<platform>.cmake,
which is regenerated wholesale. A few do not: PhysX, poly2tri and NvCloth are pinned
inside their own gems' PAL files, and Python in its platform file. Those are rewritten
in place, matched on the target name rather than the package name, because the package
names themselves are what changed.

The engine pins each package by name and hash in
cmake/3rdParty/Platform/<Platform>/BuiltInPackages_<platform>.cmake. Promotion feeds
this script the manifest written by the deployer and opens a pull request against the
engine with the result.

    tools/gen_builtin_packages.py packages/mac-arm
    tools/gen_builtin_packages.py packages/* --engine ../Engine --write
"""

import argparse
import json
import os
import re

HEADER = """#
# Copyright (c) Contributors to the Open 3D Engine Project.
# For complete copyright and license terms please see the LICENSE at the root of this distribution.
#
# SPDX-License-Identifier: Apache-2.0 OR MIT
#

# Generated from the third party package build. Do not edit by hand.
"""

# Where each platform's package list lives in the engine, and what the file is called.
# Engine paths keep their own spelling, which does not always match our platform ids.
# The engine's own spelling for each platform family, used to pick which gem PAL
# directory belongs to the platform being promoted.
PAL_NAMES = {
    "windows": "Windows",
    "linux": "Linux",
    "mac": "Mac",
    "ios": "iOS",
    "android": "Android",
    "emscripten": "Emscripten",
}

ENGINE_FILES = {
    "windows-x64": ("Windows", "BuiltInPackages_windows.cmake"),
    "windows-arm": ("Windows", "BuiltInPackages_windows_arm64.cmake"),
    "linux-x64": ("Linux", "BuiltInPackages_linux_x86_64.cmake"),
    "linux-arm": ("Linux", "BuiltInPackages_linux_aarch64.cmake"),
    "mac-arm": ("Mac", "BuiltInPackages_mac_arm64.cmake"),
    "android-arm": ("Android", "BuiltInPackages_android.cmake"),
    "android-x64": ("Android", "BuiltInPackages_android_x86_64.cmake"),
    "ios-arm": ("iOS", "BuiltInPackages_ios.cmake"),
    "ios-simulator": ("iOS", "BuiltInPackages_ios_simulator.cmake"),
    "emscripten": ("Emscripten", "BuiltInPackages_emscripten.cmake"),
}


def render(manifest):
    lines = [HEADER]
    for package in sorted(manifest["packages"], key=lambda p: p["package_name"].lower()):
        targets = " ".join(package["targets"])
        lines.append(
            f"ly_associate_package(PACKAGE_NAME {package['package_name']} "
            f"TARGETS {targets} "
            f"PACKAGE_HASH {package['sha256']})"
        )
    return "\n".join(lines) + "\n"


ASSOCIATE = re.compile(
    r"(ly_associate_package\(\s*PACKAGE_NAME\s+)(\S+)(\s+TARGETS\s+)([^)]*?)(\s+PACKAGE_HASH\s+)(\w+)(\s*\))",
    re.MULTILINE,
)


# A gem pins its packages per platform, in Platform/<Name>/ directories. Only the one
# matching the platform being promoted may be touched: the others hold that platform's
# own package names and rewriting them would point, say, Windows at a macOS build.
PLATFORM_DIRS = ("Windows", "Linux", "Mac", "Android", "iOS", "Emscripten")


def rewrite_in_place(engine, manifest, platform, exclude_paths):
    """Repoint pins that live outside BuiltInPackages, matching on target name."""
    wanted = PAL_NAMES[platform.split("-")[0]]
    by_target = {}
    for package in manifest["packages"]:
        for target in package["targets"]:
            by_target[target] = package

    changed = []
    for root, _dirs, files in os.walk(engine):
        if any(part in root for part in (".git", "build")):
            continue
        for name in files:
            if not name.endswith(".cmake"):
                continue
            path = os.path.join(root, name)
            if any(skip in path for skip in exclude_paths):
                continue

            # Skip a platform directory belonging to some other platform.
            parts = path.split(os.sep)
            other = [d for d in PLATFORM_DIRS if d in parts and d != wanted]
            if other:
                continue
            with open(path, encoding="utf8") as handle:
                text = handle.read()
            if "ly_associate_package" not in text:
                continue

            def replace(match):
                targets = match.group(4).split()
                package = by_target.get(targets[0]) if targets else None
                if package is None:
                    return match.group(0)
                return (match.group(1) + package["package_name"] + match.group(3)
                        + match.group(4) + match.group(5) + package["sha256"]
                        + match.group(7))

            updated = ASSOCIATE.sub(replace, text)
            if updated != text:
                with open(path, "w", encoding="utf8") as handle:
                    handle.write(updated)
                changed.append(os.path.relpath(path, engine))
    return changed


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("folders", nargs="+", help="folders holding built packages")
    parser.add_argument("--engine", help="engine checkout to write into")
    parser.add_argument("--write", action="store_true",
                        help="write into the engine instead of printing")
    parser.add_argument("--exclude", action="append", default=[],
                        help="package to leave out, for one the engine sources another "
                             "way (assimp arrives through FetchContent, for instance)")
    args = parser.parse_args()

    for folder in args.folders:
        manifest_path = os.path.join(folder, "packages-manifest.json")
        if not os.path.isfile(manifest_path):
            continue
        with open(manifest_path, encoding="utf8") as handle:
            manifest = json.load(handle)

        if args.exclude:
            manifest["packages"] = [
                pkg for pkg in manifest["packages"]
                if pkg["reference"].split("/")[0] not in args.exclude
            ]

        platform = manifest["platform"]
        content = render(manifest)

        if not args.write:
            print(f"# ---- {platform} ----")
            print(content)
            continue

        if not args.engine:
            raise SystemExit("--write needs --engine")
        if platform not in ENGINE_FILES:
            raise SystemExit(f"no engine location known for platform '{platform}'")

        directory, filename = ENGINE_FILES[platform]
        destination = os.path.join(args.engine, "cmake", "3rdParty", "Platform", directory, filename)
        os.makedirs(os.path.dirname(destination), exist_ok=True)
        with open(destination, "w", encoding="utf8") as handle:
            handle.write(content)
        print(f"wrote {destination} ({len(manifest['packages'])} packages)")

        # Pins that live in gem PAL files and Python's platform file are edited in
        # place; the generated file above must not also claim them.
        for touched in rewrite_in_place(args.engine, manifest, platform,
                                        exclude_paths=(os.path.join("3rdParty", "Platform"),)):
            print(f"  repointed {touched}")


if __name__ == "__main__":
    main()
