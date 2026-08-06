#
# Copyright (c) Contributors to the Open 3D Engine Project.
# For complete copyright and license terms please see the LICENSE at the root of this distribution.
#
# SPDX-License-Identifier: Apache-2.0 OR MIT
#

"""What we build, for which platforms, and how it is named.

Each package is a directory under recipes/ holding a package.yml. A directory with a
conanfile.py beside it is one we build ourselves; one without takes the recipe from
Conan Center, and the package.yml is all there is to it.

package.yml sits next to the recipe but deliberately outside it. Conan hashes a recipe's
exported files to decide whether a binary is still good, so writing a rev bump into the
conanfile would rebuild the package -- an hour, in Qt's case -- to change a number that
only affects publishing. Nothing here is exported, so editing it costs nothing.

Loaded by path from the consumer conanfile and from the deployer, so it must not import
anything beyond the standard library and PyYAML, which Conan itself depends on.
"""

import os

import yaml

RECIPES = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "recipes")

DESKTOP = (
    "windows-x64",
    "windows-arm",
    "linux-x64",
    "linux-arm",
    "mac-x64",
    "mac-arm",
)

MOBILE = (
    "android-arm",
    "android-x64",
    "ios-arm",
    "ios-simulator",
)

WEB = ("emscripten",)

# Every platform with a native toolchain, which is everything except the web.
CORE = DESKTOP + MOBILE

ALL = CORE + WEB

# Platforms that build host tooling (Qt, PySide, Python, OpenImageIO and friends).
TOOLS = DESKTOP

WINDOWS = ("windows-x64", "windows-arm")

# Names a package.yml may use in place of a list of platform ids.
GROUPS = {
    "all": ALL,
    "core": CORE,
    "desktop": DESKTOP,
    "tools": TOOLS,
    "mobile": MOBILE,
    "windows": WINDOWS,
    "web": WEB,
}

# The Conan os setting each platform targets, for deciding library file names.
CONAN_OS = {
    "windows-x64": "Windows",
    "windows-arm": "Windows",
    "linux-x64": "Linux",
    "linux-arm": "Linux",
    "mac-x64": "Macos",
    "mac-arm": "Macos",
    "android-arm": "Android",
    "android-x64": "Android",
    "ios-arm": "iOS",
    "ios-simulator": "iOS",
    "emscripten": "Emscripten",
}

_BY_OS_ARCH = {
    ("Windows", "x86_64"): "windows-x64",
    ("Windows", "armv8"): "windows-arm",
    ("Linux", "x86_64"): "linux-x64",
    ("Linux", "armv8"): "linux-arm",
    ("Macos", "x86_64"): "mac-x64",
    ("Macos", "armv8"): "mac-arm",
    ("Android", "x86_64"): "android-x64",
    ("Android", "armv8"): "android-arm",
}


def platform_id(settings):
    """Map Conan host settings to a platform id.

    A platform id is the name of the profile that builds it and the suffix of every
    package produced for it, which keeps profiles, package names and the deployer in
    agreement without a translation table.
    """
    os_name = str(settings.os)
    arch = str(settings.arch)

    if os_name == "iOS":
        sdk = settings.get_safe("os.sdk")
        return "ios-simulator" if str(sdk) == "iphonesimulator" else "ios-arm"

    if os_name == "Emscripten":
        return "emscripten"

    try:
        return _BY_OS_ARCH[(os_name, arch)]
    except KeyError:
        raise ValueError(f"no platform id for os={os_name} arch={arch}") from None


def _resolve_platforms(value, name):
    if isinstance(value, str):
        if value not in GROUPS:
            raise ValueError(
                f"{name}/package.yml: unknown platform group '{value}'; expected one of "
                f"{', '.join(sorted(GROUPS))}, or a list of platform ids"
            )
        return GROUPS[value]

    unknown = [platform for platform in value if platform not in ALL]
    if unknown:
        raise ValueError(f"{name}/package.yml: unknown platform(s) {', '.join(unknown)}")
    return tuple(value)


def _load():
    """Read every recipes/<name>/package.yml.

    Required fields:
      version    Conan version to require.
      rev        Release counter. Bump to reship a package; the CDN refuses overwrites.
      targets    Names the engine passes to find_package. Each gets a
                 Find<target>.cmake shim that includes the package's config file.
      platforms  A group name from GROUPS, or a list of platform ids.

    Optional:
      aliases    Upstream target spellings to alias, so a dependency calling
                 find_package(ZLIB) links ours rather than a system copy.
      bundle     Dependencies whose payload is merged into this package rather than
                 shipped separately, as Imath is into OpenEXR.
      payload    Payload directory name, when it differs from the recipe name.
      options    Conan options for this package, for trimming what a recipe pulls in
                 by default. Conan Center recipes tend to enable every optional format
                 or backend they support, which is rarely what a shipped package wants.

    Anything in recipes/<name>/cmake/ is copied to the package root and replaces the
    generated config file or Find module of the same name.
    """
    packages = {}
    if not os.path.isdir(RECIPES):
        return packages

    for name in sorted(os.listdir(RECIPES)):
        descriptor = os.path.join(RECIPES, name, "package.yml")
        if not os.path.isfile(descriptor):
            continue

        with open(descriptor, encoding="utf8") as handle:
            spec = yaml.safe_load(handle) or {}

        missing = [f for f in ("version", "rev", "targets", "platforms") if f not in spec]
        if missing:
            raise ValueError(f"{name}/package.yml: missing {', '.join(missing)}")

        spec["version"] = str(spec["version"])
        spec["platforms"] = _resolve_platforms(spec["platforms"], name)
        # Whether we author the recipe or take it from Conan Center.
        spec["local"] = os.path.isfile(os.path.join(RECIPES, name, "conanfile.py"))
        packages[name] = spec

    return packages


PACKAGES = _load()


def packages_for(platform):
    """Catalog entries produced for a platform, keyed by recipe name."""
    return {
        name: spec
        for name, spec in PACKAGES.items()
        if platform in spec["platforms"]
    }
