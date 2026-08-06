#
# Copyright (c) Contributors to the Open 3D Engine Project.
# For complete copyright and license terms please see the LICENSE at the root of this distribution.
#
# SPDX-License-Identifier: Apache-2.0 OR MIT
#

"""Turn resolved Conan packages into packages the engine can consume.

The engine downloads a flat `<name>.tar.xz` from a package server, extracts it into
`<unpack>/<name>/`, prepends that folder to CMAKE_MODULE_PATH and calls
find_package(<target> MODULE). This deployer produces exactly that shape, so recipes
stay ordinary Conan recipes and nothing here leaks into them.

Per package it writes four flat files:

    <package>.tar.xz
    <package>.tar.xz.SHA256SUMS          hash of the archive
    <package>.tar.xz.content.SHA256SUMS  hash of every file inside it
    <package>.PackageInfo.json           copy of the descriptor inside the archive
"""

import hashlib
import importlib.util
import json
import lzma
import os
import shutil
import stat
import tarfile

_HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(_HERE))

ARCHIVE_EXT = ".tar.xz"
HASH_EXT = ".tar.xz.SHA256SUMS"
CONTENT_HASH_EXT = ".tar.xz.content.SHA256SUMS"
MANIFEST_NAME = "SHA256SUMS"
DESCRIPTOR_NAME = "PackageInfo.json"

# Conan bookkeeping that has no place in a shipped package.
EXCLUDED_FROM_PAYLOAD = ("conaninfo.txt", "conanmanifest.txt")

_BUFFER = 1024 * 1024 * 10


def _load_catalog():
    path = os.path.join(ROOT, "tools", "catalog.py")
    spec = importlib.util.spec_from_file_location("_3p_catalog", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


catalog = _load_catalog()


# --------------------------------------------------------------------------------------
# hashing and archiving
# --------------------------------------------------------------------------------------

def _hash_file(path):
    """SHA256 of a file's contents, following symlinks.

    Following links is what lets a package built on macOS or Linux be archived and
    verified anywhere else.
    """
    hasher = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(_BUFFER), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def _payload_files(folder):
    """Every file in the staged package, relative to its root, sorted.

    Symlinks to files stay symlinks, and are hashed by what they point at. Symlinks to
    directories are walked into and their contents recorded as ordinary files, so a
    linked directory arrives as a real one holding a second copy of the content.

    That asymmetry is not an accident: it is what the engine already receives, and both
    halves matter. macOS frameworks are built out of directory links -- Qt's
    include/QtCore and every framework's Versions/Current -- and dropping them would
    ship a package with no headers. Keeping them as links instead would leave the engine
    resolving paths that climb out of the package.

    Directories are tracked by real path so a link pointing back up its own tree cannot
    send this into a loop.
    """
    found = []

    def walk(directory, ancestors):
        for entry in sorted(os.scandir(directory), key=lambda item: item.name):
            if entry.is_dir():
                resolved = os.path.realpath(entry.path)
                # Only a link back into the branch above would loop. Two names for the
                # same directory side by side, as with Versions/A and Versions/Current,
                # are both walked, which is what materialises each of them.
                if resolved in ancestors:
                    continue
                walk(entry.path, ancestors | {resolved})
            elif entry.is_file():
                found.append(os.path.relpath(entry.path, folder).replace(os.sep, "/"))
            # Anything else is a dangling symlink and is left out.

    walk(folder, {os.path.realpath(folder)})
    return sorted(found)


def _writable(tarinfo):
    """Archived files must not be read-only; the engine deletes and replaces them."""
    tarinfo.mode = tarinfo.mode | stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH
    # Fixed ownership and timestamps keep the archive byte-identical between builds.
    tarinfo.mtime = 0
    tarinfo.uid = tarinfo.gid = 0
    tarinfo.uname = tarinfo.gname = ""
    return tarinfo


def _archive(stage, relpaths, manifest_text, destination):
    with tarfile.open(destination, mode="w:xz", bufsize=_BUFFER,
                      preset=lzma.PRESET_EXTREME | 9) as tar:
        for relpath in relpaths:
            tar.add(os.path.join(stage, relpath), arcname=relpath, filter=_writable)

        manifest_path = os.path.join(stage, MANIFEST_NAME)
        with open(manifest_path, "wb") as handle:
            handle.write(manifest_text.encode("utf8"))
        tar.add(manifest_path, arcname=MANIFEST_NAME, filter=_writable)
        os.remove(manifest_path)


# --------------------------------------------------------------------------------------
# cmake generation
# --------------------------------------------------------------------------------------

_HEADER = """#
# Generated by extensions/deployers/engine_package.py. Do not edit.
#
# SPDX-License-Identifier: Apache-2.0 OR MIT
#
"""

_LIB_PATTERNS = {
    "Windows": ("{name}.lib", "lib{name}.lib", "{name}.dll.lib"),
    "Macos": ("lib{name}.a", "lib{name}.dylib", "{name}.a", "{name}.dylib"),
    "iOS": ("lib{name}.a", "lib{name}.dylib"),
    "_default": ("lib{name}.a", "lib{name}.so", "{name}.a", "{name}.so"),
}


def _find_library(lib, libdirs, os_name):
    patterns = _LIB_PATTERNS.get(os_name, _LIB_PATTERNS["_default"])
    for libdir in libdirs:
        for pattern in patterns:
            candidate = os.path.join(libdir, pattern.format(name=lib))
            if os.path.isfile(candidate):
                return candidate
    return None


def _payload_relative(relative, payload):
    """A path written relative to the payload, as a config file has to express it."""
    prefix = "${CMAKE_CURRENT_LIST_DIR}" if payload == "." else "${CMAKE_CURRENT_LIST_DIR}/" + payload
    return f"{prefix}/{relative.strip('/')}"


def _cmake_path(absolute, package_folder, payload):
    """Rebase a path in the Conan cache onto where it lands inside the package.

    cpp_info describes the package as it sits in the cache; the deployer copies that
    tree under `<payload>/`, so every emitted path has to be translated or the config
    file would point at a cache folder that consumers do not have. A payload of "."
    means the tree sits at the package root instead, which is how the engine expects to
    find Python's framework.
    """
    rel = os.path.relpath(absolute, package_folder).replace(os.sep, "/")
    if rel.startswith(".."):
        return None
    rel = "" if rel == "." else "/" + rel
    prefix = "${CMAKE_CURRENT_LIST_DIR}" if payload == "." else "${CMAKE_CURRENT_LIST_DIR}/" + payload
    return prefix + rel


def _version_variables(target, version):
    parts = str(version).split(".")
    while len(parts) < 3:
        parts.append("0")
    major, minor, patch = parts[0], parts[1], parts[2]
    return "\n".join([
        f'set({target}_VERSION_STRING "{version}")',
        f'set({target}_VERSION "{version}")',
        f'set({target}_VERSION_MAJOR "{major}")',
        f'set({target}_VERSION_MINOR "{minor}")',
        f'set({target}_VERSION_PATCH "{patch}")',
        f'set({target}_MAJOR_VERSION "{major}")',
        f'set({target}_MINOR_VERSION "{minor}")',
        f'set({target}_PATCH_VERSION "{patch}")',
    ])


def _unique(items):
    seen, result = set(), []
    for item in items:
        if item is not None and item not in seen:
            seen.add(item)
            result.append(item)
    return result


def collect_usage(nodes, payload, os_name):
    """Merge the build information of a package and anything bundled into it."""
    includedirs, resolved, missing = [], [], []
    system_libs, frameworks, defines = [], [], []

    for node in nodes:
        cpp_info = node.conanfile.cpp_info.aggregated_components()
        package_folder = node.conanfile.package_folder

        includedirs += [_cmake_path(d, package_folder, payload) for d in cpp_info.includedirs or []]
        for lib in cpp_info.libs or []:
            found = _find_library(lib, cpp_info.libdirs or [], os_name)
            if found:
                resolved.append(_cmake_path(found, package_folder, payload))
            else:
                missing.append(lib)
        system_libs += cpp_info.system_libs or []
        frameworks += cpp_info.frameworks or []
        defines += cpp_info.defines or []

    return {
        "includedirs": _unique(includedirs),
        "libraries": _unique(resolved),
        "missing": _unique(missing),
        "system_libs": _unique(system_libs),
        "frameworks": _unique(frameworks),
        "defines": _unique(defines),
    }


def usage_per_target(targets, nodes, payload, os_name):
    """Decide which build information belongs to each target.

    A package that bundles another (OpenEXR shipping Imath) declares one target per
    bundled package, in the same order. Pairing them keeps 3rdParty::Imath pointing at
    Imath's libraries rather than everything in the archive. When the counts do not
    line up there is nothing to pair on, so every target describes the whole package.
    """
    shared = collect_usage(nodes, payload, os_name)
    if len(targets) > 1 and len(targets) == len(nodes):
        paired = {}
        for target, node in zip(targets, nodes):
            usage = collect_usage([node], payload, os_name)
            # Libraries are per target, but the headers are one tree: OpenEXR's own
            # headers include Imath's by name, so a consumer of either target needs
            # every include directory in the package.
            usage["includedirs"] = shared["includedirs"]
            usage["defines"] = shared["defines"]
            paired[target] = usage
        return paired

    return {t: shared for t in targets}


def _generate_config(name, version, targets, usage_map, aliases=None):
    """Build a config file that declares the engine's 3rdParty:: targets.

    Modelled on the hand written Find files this replaces: real imported targets
    rather than interface ones, paths relative to the package, and the upstream
    variables so the package also works as a drop in for CMake's own module.
    """
    body = [_HEADER]
    missing = _unique([m for usage in usage_map.values() for m in usage["missing"]])
    if missing:
        body.append(f"# Unresolved libraries reported by the recipe: {', '.join(missing)}\n")

    for target in targets:
        usage = usage_map[target]
        includedirs = usage["includedirs"]
        resolved = usage["libraries"]

        guard = f"3rdParty::{target}"
        lines = [
            f'if (NOT TARGET {guard})',
            f'    set(_target "{guard}")',
        ]

        if includedirs:
            joined = " ".join(f'"{d}"' for d in includedirs)
            lines += [
                f"    set({target}_INCLUDE_DIRS {joined})",
                f"    set({target}_INCLUDE_DIR ${{{target}_INCLUDE_DIRS}})",
            ]

        if resolved:
            joined = " ".join(f'"{p}"' for p in resolved)
            lines += [
                f"    set({target}_LIBRARIES {joined})",
                f"    set({target}_LIBRARY ${{{target}_LIBRARIES}})",
            ]

        lines.append("    " + _version_variables(target, version).replace("\n", "\n    "))
        lines.append(f"    set({target}_FOUND True)")
        lines.append("")

        kind = "STATIC" if resolved else "INTERFACE"
        lines.append(f"    add_library(${{_target}} {kind} IMPORTED GLOBAL)")

        # Upstream-spelled aliases let this package stand in for CMake's own module,
        # so a dependency doing find_package(ZLIB) links ours rather than the system copy.
        for alias in (aliases or {}).get(target, []):
            lines.append(f"    add_library({alias} ALIAS ${{_target}})")

        if resolved:
            lines.append(f'    set_target_properties(${{_target}} PROPERTIES IMPORTED_LOCATION "{resolved[0]}")')

        # set_target_properties reads its arguments as property/value pairs, so a list
        # has to arrive as one semicolon separated value rather than several words.
        link = list(resolved[1:])
        link += list(usage["system_libs"])
        link += [f"-framework {f}" for f in usage["frameworks"]]
        if link:
            joined = ";".join(link)
            lines.append(
                f'    set_target_properties(${{_target}} PROPERTIES INTERFACE_LINK_LIBRARIES "{joined}")'
            )

        if usage["defines"]:
            joined = ";".join(usage["defines"])
            lines.append(
                f'    set_target_properties(${{_target}} PROPERTIES INTERFACE_COMPILE_DEFINITIONS "{joined}")'
            )

        if includedirs:
            # O3DE patches SYSTEM includes for toolchains that get them wrong; use its
            # version when present so warnings from third party headers stay suppressed.
            lines += [
                "",
                "    if (COMMAND ly_target_include_system_directories)",
                f"        ly_target_include_system_directories(TARGET ${{_target}} INTERFACE ${{{target}_INCLUDE_DIRS}})",
                "    else()",
                f"        target_include_directories(${{_target}} SYSTEM INTERFACE ${{{target}_INCLUDE_DIRS}})",
                "    endif()",
            ]

        lines += [
            "",
            "    if (NOT LY_VERSION_ENGINE_NAME)",
            f'        message(STATUS "Using the O3DE version of {target} from ${{CMAKE_CURRENT_LIST_DIR}}")',
            "    endif()",
            "endif()",
            "",
        ]
        body.append("\n".join(lines))

    return "\n".join(body)


def _generate_find_shim(name, target):
    """Module mode entry point. The engine calls find_package(<target> MODULE)."""
    return (
        f"{_HEADER}\n"
        f"# Backwards compatible entry point for find_package({target} MODULE).\n"
        f'include("${{CMAKE_CURRENT_LIST_DIR}}/{name}-config.cmake")\n'
    )


# --------------------------------------------------------------------------------------
# staging
# --------------------------------------------------------------------------------------

def _copy_payload(source, destination):
    def ignore(directory, names):
        if os.path.abspath(directory) == os.path.abspath(source):
            return set(EXCLUDED_FROM_PAYLOAD) & set(names)
        return set()

    shutil.copytree(source, destination, symlinks=True, ignore=ignore, dirs_exist_ok=True)


def _license_path(stage, payload):
    """Package relative path to a license file, preferring Conan's licenses folder."""
    prefix = "" if payload == "." else payload + "/"
    licenses = os.path.join(stage, payload, "licenses")
    if os.path.isdir(licenses):
        # A file, not whatever sorts first: a package that licenses several components
        # can have directories in here, and the engine expects LicenseFile to be readable.
        names = [n for n in sorted(os.listdir(licenses))
                 if os.path.isfile(os.path.join(licenses, n))]
        if names:
            return f"{prefix}licenses/{names[0]}"

    root = os.path.join(stage, payload)
    for name in sorted(os.listdir(root)) if os.path.isdir(root) else []:
        if name.upper().startswith(("LICENSE", "COPYING")):
            return f"{prefix}{name}"
    return None


def _copy_curated_cmake(name, stage):
    """Copy hand written cmake for this recipe onto the package root.

    Whatever recipes/<name>/cmake/ contains lands at the top of the package, which is
    also where a curated config file or Find module overrides the generated one. Qt uses
    this for its Platform/ subdirectory as well as its config file.
    """
    source = os.path.join(ROOT, "recipes", name, "cmake")
    if not os.path.isdir(source):
        return set()

    shutil.copytree(source, stage, symlinks=True, dirs_exist_ok=True)
    return set(os.listdir(source))


def _source_url(conanfile):
    """Where this package's source came from, for the descriptor's URL.

    A recipe states this once, in conandata.yml, and it says something more useful than a
    project's home page: it is the exact archive the package was built from. The shape
    varies -- some recipes key sources by version, others by version then os and arch --
    so the first url found wins.
    """
    def search(value):
        if isinstance(value, dict):
            url = value.get("url")
            if isinstance(url, str):
                return url
            # Several recipes list mirrors; the first is the one to record.
            if isinstance(url, (list, tuple)) and url and isinstance(url[0], str):
                return url[0]
            for nested in value.values():
                found = search(nested)
                if found:
                    return found
        elif isinstance(value, (list, tuple)):
            for nested in value:
                found = search(nested)
                if found:
                    return found
        return None

    data = getattr(conanfile, "conan_data", None) or {}
    found = search(data.get("sources"))
    if found:
        return found

    # A recipe that clones instead of downloading an archive has no sources entry; the
    # repository it clones is the same fact.
    git_url = getattr(conanfile, "_git_url", None)
    return git_url if isinstance(git_url, str) else ""


def _declared(node, spec, key, default=None):
    """What the recipe says about its own packaging, wherever it still says it.

    A recipe declares these as class attributes, which arrive on the conanfile instance.
    The catalog entry is consulted only for the recipes not yet converted.
    """
    value = getattr(node.conanfile, key, None)
    if value is not None:
        return value
    return spec.get(key, default)


def _engine_targets(node, spec, bundles):
    """The names the engine will pass to find_package for this package.

    That is exactly what cmake_file_name means, so a recipe declares its engine target by
    setting it and nothing is repeated anywhere else.

    A package that carries another and answers to its name too says so with
    bundle_targets, naming which of its bundled packages stay visible. Only OpenEXR does:
    it ships Imath, and the engine has always registered both names. The rest of a
    package's bundles are implementation detail and deliberately do not appear.
    """
    targets = []
    primary = node.conanfile.cpp_info.get_property("cmake_file_name")
    if primary:
        targets.append(primary)

    public = _declared(node, spec, "bundle_targets") or []
    for bundled in bundles:
        if str(bundled.ref.name) not in public:
            continue
        extra = bundled.conanfile.cpp_info.get_property("cmake_file_name")
        if extra and extra not in targets:
            targets.append(extra)

    if not targets:
        raise RuntimeError(
            f"{node.ref.name} does not set cmake_file_name in package_info, so there is "
            f"no name for the engine to call find_package with"
        )
    return targets


def _build_package(node, spec, platform, staging_root, output_folder, bundles, os_name):
    conanfile = node.conanfile
    name = str(node.ref.name)
    version = str(node.ref.version)
    package_name = f"{name}-{version}-rev{_declared(node, spec, 'rev', 1)}-{platform}"
    payload = _declared(node, spec, "payload") or name

    stage = os.path.join(staging_root, package_name)
    if os.path.isdir(stage):
        shutil.rmtree(stage)
    os.makedirs(stage)

    payload_root = stage if payload == "." else os.path.join(stage, payload)
    _copy_payload(conanfile.package_folder, payload_root)
    for bundled in bundles:
        _copy_payload(bundled.conanfile.package_folder, payload_root)

    curated = _copy_curated_cmake(name, stage)

    targets = _engine_targets(node, spec, bundles)
    config_name = f"{name}-config.cmake"
    if config_name not in curated:
        usage_map = usage_per_target(targets, [node] + bundles, payload, os_name)

        # Recipes describe where their headers are; the engine sometimes includes them
        # from somewhere else. poly2tri installs poly2tri/poly2tri.h and engine code asks
        # for <poly2tri.h>, so the directory holding the header goes on the search path
        # as well. Paths are relative to the payload, as they appear in the package.
        for extra in _declared(node, spec, "includedirs") or []:
            for usage in usage_map.values():
                usage["includedirs"] = _unique(
                    usage["includedirs"] + [_payload_relative(extra, payload)]
                )

        # Definitions the engine expects a package to carry that its recipe knows nothing
        # about: HAVE_BENCHMARK is O3DE's own switch for the benchmark code in its tests,
        # and the package is what has always turned it on.
        extra_defines = _declared(node, spec, "defines") or []
        if extra_defines:
            for usage in usage_map.values():
                usage["defines"] = _unique(usage["defines"] + list(extra_defines))
        config = _generate_config(name, version, targets, usage_map,
                                  _declared(node, spec, "aliases"))
        with open(os.path.join(stage, config_name), "w", encoding="utf8") as handle:
            handle.write(config)

    for target in targets:
        shim_name = f"Find{target}.cmake"
        if shim_name in curated:
            continue
        with open(os.path.join(stage, shim_name), "w", encoding="utf8") as handle:
            handle.write(_generate_find_shim(name, target))

    license_file = _license_path(stage, payload)
    if not license_file:
        raise RuntimeError(f"{package_name}: no license file found in the package payload")

    license_name = conanfile.license
    if isinstance(license_name, (list, tuple)):
        license_name = " AND ".join(str(item) for item in license_name)

    descriptor = {
        "PackageName": package_name,
        "URL": conanfile.homepage or conanfile.url or _source_url(conanfile),
        "License": str(license_name or "custom"),
        "LicenseFile": license_file,
    }
    descriptor_path = os.path.join(stage, DESCRIPTOR_NAME)
    with open(descriptor_path, "w", encoding="utf8") as handle:
        json.dump(descriptor, handle, indent=4)
        handle.write("\n")

    relpaths = _payload_files(stage)
    manifest = "".join(f"{_hash_file(os.path.join(stage, rel))} *{rel}\n" for rel in relpaths)

    archive_path = os.path.join(output_folder, package_name + ARCHIVE_EXT)
    _archive(stage, relpaths, manifest, archive_path)

    archive_hash = _hash_file(archive_path)
    _write(os.path.join(output_folder, package_name + HASH_EXT),
           f"{archive_hash} *{package_name + ARCHIVE_EXT}\n")
    _write(os.path.join(output_folder, package_name + CONTENT_HASH_EXT), manifest)
    shutil.copyfile(descriptor_path, os.path.join(output_folder, f"{package_name}.{DESCRIPTOR_NAME}"))

    print(f"    {package_name + ARCHIVE_EXT}  {archive_hash}")
    return {
        "package_name": package_name,
        "archive": package_name + ARCHIVE_EXT,
        "sha256": archive_hash,
        "targets": list(targets),
        "reference": f"{name}/{version}",
        "platform": platform,
    }


def _write(path, text):
    with open(path, "w", encoding="utf8") as handle:
        handle.write(text)


# --------------------------------------------------------------------------------------
# entry point
# --------------------------------------------------------------------------------------

def deploy(graph, output_folder, **kwargs):
    nodes = {}
    for node in graph.nodes:
        if node is graph.root or node.conanfile.package_folder is None:
            continue
        if getattr(node, "context", "host") != "host":
            continue  # build tools are not shipped
        nodes[str(node.ref.name)] = node

    # Installing a single package gives a synthetic root that carries no settings, so
    # fall back to what the packages themselves were built with.
    if not nodes:
        print("nothing to package")
        return

    # The caller knows the target; the graph does not always. Installing a single package
    # gives a synthetic root with no settings, and a header only package can legitimately
    # have none of its own, so neither is a reliable place to ask.
    platform = os.environ.get("O3DE_TARGET_PLATFORM")
    if not platform:
        for node in nodes.values():
            if node.conanfile.settings.get_safe("os"):
                platform = catalog.platform_id(node.conanfile.settings)
                break
    if not platform:
        raise RuntimeError(
            "set O3DE_TARGET_PLATFORM: the target cannot be inferred from this graph"
        )

    entries = catalog.packages_for(platform)

    bundled_into_others = {
        bundled
        for spec in entries.values()
        for bundled in spec.get("bundle", [])
    }

    os.makedirs(output_folder, exist_ok=True)
    staging_root = os.path.join(output_folder, ".stage")
    if os.path.isdir(staging_root):
        shutil.rmtree(staging_root)
    os.makedirs(staging_root)

    print(f"Building engine packages for {platform}")
    produced, absent = [], []
    for name, spec in entries.items():
        if name in bundled_into_others:
            continue
        node = nodes.get(name)
        if node is None:
            # Expected when installing a single package; worth reporting otherwise.
            absent.append(name)
            continue
        # A bundle that quietly resolves to nothing produces a package that looks right
        # and cannot be linked against, days later and somewhere else, so it stops here.
        wanted = _declared(node, spec, "bundle") or []
        missing = [b for b in wanted if b not in nodes]
        if missing:
            raise RuntimeError(
                f"{name} bundles {', '.join(missing)}, which the graph does not offer a "
                f"package folder for. Conan skips the binaries of static dependencies "
                f"that a shared library has already absorbed; tools.graph:skip_binaries "
                f"is set to False in profiles/_common to prevent exactly that."
            )
        bundles = [nodes[b] for b in wanted]
        produced.append(_build_package(
            node, spec, platform, staging_root, output_folder, bundles,
            catalog.CONAN_OS[platform],
        ))

    if absent:
        print(f"  not in this graph, so not packaged: {', '.join(sorted(absent))}")

    shutil.rmtree(staging_root, ignore_errors=True)

    # Merged rather than overwritten, so building one package does not drop the record
    # of everything else already sitting in this folder.
    manifest_path = os.path.join(output_folder, "packages-manifest.json")
    by_name = {}
    if os.path.isfile(manifest_path):
        with open(manifest_path, encoding="utf8") as handle:
            existing = json.load(handle)
        if existing.get("platform") == platform:
            # Entries whose archive is gone are dropped rather than carried forward. A
            # version bump leaves the old package's record behind otherwise, and the
            # engine is then pinned to a file that is not there to download.
            by_name = {
                entry["package_name"]: entry
                for entry in existing.get("packages", [])
                if os.path.isfile(os.path.join(output_folder,
                                               entry["package_name"] + ARCHIVE_EXT))
            }
    by_name.update({entry["package_name"]: entry for entry in produced})

    merged = sorted(by_name.values(), key=lambda entry: entry["package_name"].lower())
    with open(manifest_path, "w", encoding="utf8") as handle:
        json.dump({"platform": platform, "packages": merged}, handle, indent=2)
        handle.write("\n")

    print(f"{len(produced)} package(s) written to {output_folder}")
