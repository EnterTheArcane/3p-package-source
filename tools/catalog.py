#
# Copyright (c) Contributors to the Open 3D Engine Project.
# For complete copyright and license terms please see the LICENSE at the root of this distribution.
#
# SPDX-License-Identifier: Apache-2.0 OR MIT
#

"""What we build and for which platforms.

Every package is a directory under recipes/ holding a conanfile.py we own. The recipe is
the whole description: its version, its release counter, the platforms it ships for, and
through package_info the name the engine calls find_package with.

The consumer has to know which packages a platform wants before Conan has a graph to ask,
so version, rev and platforms are read straight out of the recipe source. Conan's own
inspection reports only the attributes it knows about, and importing the recipe would tie
this to an interpreter that has Conan installed, which the command line does not.

Loaded by path from the consumer conanfile and from the deployer, so it must not import
anything beyond the standard library.
"""

import ast
import os

RECIPES = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "recipes")

# Class attributes a recipe declares for itself. Everything else the catalog needs comes
# from Conan at graph time; these are the facts that have to be known before there is one.
_FROM_RECIPE = ("version", "rev", "platforms")

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

# Names a recipe may use in place of a list of platform ids.
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
                f"{name}: unknown platform group '{value}'; expected one of "
                f"{', '.join(sorted(GROUPS))}, or a list of platform ids"
            )
        return GROUPS[value]

    unknown = [platform for platform in value if platform not in ALL]
    if unknown:
        raise ValueError(f"{name}: unknown platform(s) {', '.join(unknown)}")
    return tuple(value)


def _recipe_attributes(path):
    """Class attributes of a conanfile, read without importing or running it.

    The consumer has to know which packages a platform wants before Conan has a graph to
    ask, so this reads the declaration straight out of the source. Parsing rather than
    importing keeps the catalog free of a Conan dependency, and means a recipe cannot run
    code just by being listed.
    """
    with open(path, encoding="utf8") as handle:
        tree = ast.parse(handle.read(), filename=path)

    definition = next((node for node in tree.body if isinstance(node, ast.ClassDef)), None)
    if definition is None:
        return {}

    attributes = {}
    for statement in definition.body:
        if not isinstance(statement, ast.Assign) or len(statement.targets) != 1:
            continue
        target = statement.targets[0]
        if not isinstance(target, ast.Name):
            continue
        try:
            attributes[target.id] = ast.literal_eval(statement.value)
        except ValueError:
            # Conan's own inspection reports only the attributes it knows about, so these
            # have to be read from the source, and reading the source means they have to
            # be literals. Silently skipping one would drop the package from the
            # inventory, which looks exactly like a package nobody asked for.
            if target.id in _FROM_RECIPE:
                raise ValueError(
                    f"{path}: {target.id} has to be written as a literal, because the "
                    f"catalog reads it without running the recipe"
                ) from None
    return attributes


def _load():
    """Read what every recipe declares about itself.

      version    The version built, which also names the package.
      rev        Release counter. Bump to reship; the CDN refuses overwrites.
      platforms  A group name from GROUPS, or a list of platform ids. A recipe without
                 this is a build tool that never ships, which is what llvm is.

    Everything else the deployer needs -- the engine's target name, bundles, payload
    directory, extra include directories and defines -- comes from the recipe too, but at
    graph time, off the resolved conanfile. Anything in recipes/<name>/cmake/ is copied
    to the package root and replaces the generated config or Find module of that name.
    """
    packages = {}
    if not os.path.isdir(RECIPES):
        return packages

    for name in sorted(os.listdir(RECIPES)):
        recipe = os.path.join(RECIPES, name, "conanfile.py")
        if not os.path.isfile(recipe):
            continue
        spec = {key: value for key, value in _recipe_attributes(recipe).items()
                if key in _FROM_RECIPE}
        # Declaring platforms is what makes a recipe an engine package. A recipe without
        # them is a build tool that never ships, which is what llvm is.
        if "platforms" not in spec:
            continue

        missing = [f for f in ("version", "rev") if f not in spec]
        if missing:
            raise ValueError(f"{name}: missing {', '.join(missing)}")

        spec["version"] = str(spec["version"])
        spec["platforms"] = _resolve_platforms(spec["platforms"], name)
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
