#!/usr/bin/env python3
#
# Copyright (c) Contributors to the Open 3D Engine Project.
# For complete copyright and license terms please see the LICENSE at the root of this distribution.
#
# SPDX-License-Identifier: Apache-2.0 OR MIT
#

"""Check built packages against what the engine expects of them.

The engine is unforgiving about package shape and gives poor diagnostics when it is
wrong, so every rule it relies on is asserted here instead: the four files, the hash
files, an archive that extracts without a wrapper directory, a complete and correct
manifest, a descriptor with the required fields, and a Find module per declared
target. With CMake available it also configures a throwaway project that consumes
the package the way the engine does.
"""

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile

ARCHIVE_EXT = ".tar.xz"
HASH_EXT = ".tar.xz.SHA256SUMS"
CONTENT_HASH_EXT = ".tar.xz.content.SHA256SUMS"
MANIFEST_NAME = "SHA256SUMS"
DESCRIPTOR_NAME = "PackageInfo.json"
# O3DE only requires PackageInfo.json itself for package activation, while the
# license scanner consumes LicenseFile.  URL is useful provenance when a recipe
# provides it, but it is not part of the engine's package contract.
REQUIRED_FIELDS = ("PackageName", "License", "LicenseFile")


# Load paths that resolve relative to the package or against the OS itself, which is
# all a relocatable package should contain. Anything else names the build machine.
PORTABLE_PREFIXES = ("@rpath", "@loader_path", "@executable_path",
                     "/usr/lib", "/System/Library")

MACHO_MAGIC = (b"\xcf\xfa\xed\xfe", b"\xce\xfa\xed\xfe", b"\xca\xfe\xba\xbe")
ELF_MAGIC = b"\x7fELF"


class Failures:
    def __init__(self):
        self.items = []

    def check(self, condition, message):
        if not condition:
            self.items.append(message)
        return condition


def sha256(path):
    hasher = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def parse_manifest(text, failures, source):
    """Parse `<hash> *<path>` lines the way the engine's cmake does."""
    entries = {}
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        space = line.find(" ")
        if not failures.check(space == 64, f"{source}: malformed line: {line[:80]}"):
            continue
        entries[line[space + 2:]] = line[:space]
    return entries


def validate(archive, failures):
    folder = os.path.dirname(archive)
    package = os.path.basename(archive)[: -len(ARCHIVE_EXT)]
    print(f"  {package}")

    hash_file = os.path.join(folder, package + HASH_EXT)
    content_hash_file = os.path.join(folder, package + CONTENT_HASH_EXT)
    descriptor_file = os.path.join(folder, f"{package}.{DESCRIPTOR_NAME}")

    for path in (hash_file, content_hash_file, descriptor_file):
        failures.check(os.path.isfile(path), f"{package}: missing {os.path.basename(path)}")
    if failures.items:
        return

    # The engine refuses a package whose archive does not match the published hash.
    with open(hash_file, encoding="utf8") as handle:
        declared = parse_manifest(handle.read(), failures, package + HASH_EXT)
    failures.check(
        declared.get(package + ARCHIVE_EXT) == sha256(archive),
        f"{package}: archive hash does not match {HASH_EXT}",
    )

    extracted = os.path.realpath(tempfile.mkdtemp(prefix="validate-"))
    try:
        with tarfile.open(archive, mode="r:xz") as tar:
            names = tar.getnames()
            # The engine extracts into <unpack>/<package>/, so a top level directory
            # named after the package would nest the payload one level too deep.
            failures.check(
                not any(n == package or n.startswith(package + "/") for n in names),
                f"{package}: archive contains a redundant {package}/ wrapper directory",
            )
            failures.check(MANIFEST_NAME in names, f"{package}: archive has no {MANIFEST_NAME}")
            tar.extractall(extracted, filter="tar")

        manifest_path = os.path.join(extracted, MANIFEST_NAME)
        if not failures.check(os.path.isfile(manifest_path), f"{package}: no extracted {MANIFEST_NAME}"):
            return
        with open(manifest_path, encoding="utf8") as handle:
            manifest_text = handle.read()
        manifest = parse_manifest(manifest_text, failures, MANIFEST_NAME)

        with open(content_hash_file, encoding="utf8") as handle:
            failures.check(
                handle.read() == manifest_text,
                f"{package}: {CONTENT_HASH_EXT} differs from the archive's {MANIFEST_NAME}",
            )

        on_disk = set()
        for current, _dirs, files in os.walk(extracted):
            for name in files:
                rel = os.path.relpath(os.path.join(current, name), extracted).replace(os.sep, "/")
                if rel != MANIFEST_NAME:
                    on_disk.add(rel)

        for missing in sorted(on_disk - set(manifest)):
            failures.items.append(f"{package}: {missing} is in the archive but not the manifest")
        for absent in sorted(set(manifest) - on_disk):
            failures.items.append(f"{package}: {absent} is in the manifest but not the archive")

        for rel, expected in sorted(manifest.items()):
            path = os.path.join(extracted, rel)
            if os.path.isfile(path):
                failures.check(sha256(path) == expected, f"{package}: {rel} hash mismatch")

        descriptor_in_archive = os.path.join(extracted, DESCRIPTOR_NAME)
        if not failures.check(os.path.isfile(descriptor_in_archive), f"{package}: no {DESCRIPTOR_NAME}"):
            return
        with open(descriptor_in_archive, encoding="utf8") as handle:
            descriptor = json.load(handle)

        for field in REQUIRED_FIELDS:
            failures.check(descriptor.get(field), f"{package}: {DESCRIPTOR_NAME} has no {field}")
        failures.check(
            descriptor.get("PackageName") == package,
            f"{package}: PackageName is '{descriptor.get('PackageName')}'",
        )
        license_file = descriptor.get("LicenseFile")
        if license_file:
            failures.check(
                os.path.isfile(os.path.join(extracted, license_file)),
                f"{package}: LicenseFile '{license_file}' is not in the package",
            )

        with open(descriptor_file, encoding="utf8") as handle:
            failures.check(
                json.load(handle) == descriptor,
                f"{package}: the published {DESCRIPTOR_NAME} differs from the one inside the archive",
            )

        modules = [n[len("Find"):-len(".cmake")] for n in os.listdir(extracted)
                   if n.startswith("Find") and n.endswith(".cmake")]
        failures.check(modules, f"{package}: no Find<target>.cmake at the package root")
        hermetic(extracted, package, failures)
        probe(extracted, modules, package, failures)
    finally:
        shutil.rmtree(extracted, ignore_errors=True)


def hermetic(extracted, package, failures):
    """Check that nothing in the package points at the machine that built it.

    A dependency found on the build machine rather than supplied by us links by absolute
    path, and the failure lands on whoever unpacks the package somewhere else. That is
    invisible in a build log and invisible in the package contents, so it is asserted
    here. openimageio shipped this way against Homebrew's WebP.
    """
    for root, _, names in os.walk(extracted):
        for name in names:
            path = os.path.join(root, name)
            if os.path.islink(path):
                continue
            try:
                with open(path, "rb") as handle:
                    magic = handle.read(4)
            except OSError:
                continue
            if magic in MACHO_MAGIC:
                found = [(d, d.startswith(PORTABLE_PREFIXES))
                         for d in macho_dependencies(path)]
            elif magic == ELF_MAGIC:
                found = [(d, not os.path.isabs(d)) for d in elf_dependencies(path)]
            else:
                continue

            for dependency, portable in found:
                failures.check(
                    portable,
                    f"{package}: {os.path.relpath(path, extracted)} loads "
                    f"'{dependency}', which is not part of the package",
                )


def macho_dependencies(path):
    """The load paths of a Mach-O file, ignoring otool's own headers.

    otool prefixes dependency lines with a tab and starts each file, and each
    architecture of a universal binary, with an unindented header. Matching on the
    indent keeps those headers from being read as dependencies.
    """
    if not shutil.which("otool"):
        return []
    result = subprocess.run(["otool", "-L", path], capture_output=True, text=True)
    return [line.strip().split(" ")[0]
            for line in result.stdout.splitlines() if line.startswith("\t")]


def elf_dependencies(path):
    """The library names and search paths recorded in an ELF file.

    NEEDED entries are normally bare sonames the loader resolves at run time, and a
    RUNPATH is normally relative to $ORIGIN. An absolute path in either is a reference
    to the machine that did the build, which is what the caller rejects.
    """
    if not shutil.which("readelf"):
        return []
    result = subprocess.run(["readelf", "-d", path], capture_output=True, text=True)

    found = []
    for line in result.stdout.splitlines():
        if "(NEEDED)" in line or "(RPATH)" in line or "(RUNPATH)" in line:
            value = line.partition("[")[2].rpartition("]")[0]
            found += [entry for entry in value.split(":") if entry]
    return found


def probe(extracted, modules, package, failures):
    """Resolve the package the way the engine does, with CMake itself.

    A config file can be well formed and still fail to produce a usable target, which
    would surface as a confusing engine configure error much later.
    """
    cmake = shutil.which("cmake")
    if not cmake:
        return

    # A real project, not cmake -P: script mode cannot create targets.
    escaped = extracted.replace("\\", "/")
    for target in modules:
        project = "\n".join([
            "cmake_minimum_required(VERSION 3.22)",
            "project(probe C CXX)",
            f'list(PREPEND CMAKE_MODULE_PATH "{escaped}")',
            f"find_package({target} REQUIRED MODULE)",
            # Most packages export 3rdParty::<target>. Component packages such as Qt
            # export 3rdParty::<target>::<Component> instead and never define the bare
            # name, so the presence of the target cannot be required outright; what must
            # hold either way is that the module reported itself found.
            f"if (NOT {target}_FOUND)",
            f'    message(FATAL_ERROR "{target}_FOUND was not set")',
            "endif()",
            f"if (TARGET 3rdParty::{target})",
            f"    get_target_property(_loc 3rdParty::{target} IMPORTED_LOCATION)",
            '    if (_loc AND NOT EXISTS "${_loc}")',
            '        message(FATAL_ERROR "IMPORTED_LOCATION does not exist: ${_loc}")',
            "    endif()",
            "endif()",
        ])
        workdir = os.path.realpath(tempfile.mkdtemp(prefix="probe-"))
        try:
            with open(os.path.join(workdir, "CMakeLists.txt"), "w", encoding="utf8") as handle:
                handle.write(project)
            result = subprocess.run(
                [cmake, "-S", workdir, "-B", os.path.join(workdir, "build")],
                capture_output=True, text=True,
            )
            if result.returncode != 0:
                detail = [line for line in (result.stderr or result.stdout).strip().splitlines() if line.strip()]
                failures.items.append(
                    f"{package}: find_package({target}) failed: {detail[0] if detail else '?'}"
                )
        finally:
            shutil.rmtree(workdir, ignore_errors=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("folder", help="folder holding built packages")
    args = parser.parse_args()

    archives = sorted(
        os.path.join(args.folder, name)
        for name in os.listdir(args.folder)
        if name.endswith(ARCHIVE_EXT)
    )
    if not archives:
        raise SystemExit(f"no {ARCHIVE_EXT} packages in {args.folder}")

    print(f"Validating {len(archives)} package(s) in {args.folder}")
    failures = Failures()
    for archive in archives:
        validate(archive, failures)

    if failures.items:
        print(f"\n{len(failures.items)} problem(s):", file=sys.stderr)
        for item in failures.items:
            print(f"  - {item}", file=sys.stderr)
        raise SystemExit(1)
    print("\nAll packages satisfy the engine contract.")


if __name__ == "__main__":
    main()
