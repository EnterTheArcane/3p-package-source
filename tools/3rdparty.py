#!/usr/bin/env python3
#
# Copyright (c) Contributors to the Open 3D Engine Project.
# For complete copyright and license terms please see the LICENSE at the root of this distribution.
#
# SPDX-License-Identifier: Apache-2.0 OR MIT
#

"""Build third party packages for a target platform.

Wraps the Conan commands so the long invocations stay in one place. Both the host
and build profiles are always passed explicitly: without them Conan falls back to
the user's default profile, which may carry settings or requirement overrides that
have no business in a shipped package.
"""

import argparse
import importlib.util
import json
import os
import platform
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROFILES = os.path.join(ROOT, "profiles")
RECIPES = os.path.join(ROOT, "recipes")
CONSUMER = os.path.join(ROOT, "consumer", "conanfile.py")
DEPLOYER = os.path.join(ROOT, "extensions", "deployers", "engine_package.py")
LOCKFILE = os.path.join(ROOT, "conan.lock")


def _load_catalog():
    path = os.path.join(ROOT, "tools", "catalog.py")
    spec = importlib.util.spec_from_file_location("_3p_catalog", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


catalog = _load_catalog()


def native_platform():
    """The platform id of the machine we are running on, used as the build profile."""
    system = platform.system()
    machine = platform.machine().lower()
    arm = machine in ("arm64", "aarch64")
    if system == "Darwin":
        return "mac-arm" if arm else "mac-x64"
    if system == "Linux":
        return "linux-arm" if arm else "linux-x64"
    if system == "Windows":
        return "windows-arm" if arm else "windows-x64"
    raise SystemExit(f"unsupported build machine: {system}/{machine}")


def run(args, env=None):
    print("+", " ".join(args), flush=True)
    return subprocess.run(args, cwd=ROOT, check=True, env=env)


def local_recipes():
    if not os.path.isdir(RECIPES):
        return []
    return sorted(
        name
        for name in os.listdir(RECIPES)
        if os.path.isfile(os.path.join(RECIPES, name, "conanfile.py"))
    )


def profile_args(target):
    if target not in catalog.ALL:
        raise SystemExit(f"unknown platform '{target}'; see '3rdparty.py platforms'")
    return [
        "-pr:h", os.path.join(PROFILES, target),
        "-pr:b", os.path.join(PROFILES, native_platform()),
    ]


def install_args(target, only=None, deploy_to=None, rebuild=False):
    args = ["conan", "install", CONSUMER if not only else "--requires"]
    if only:
        spec = catalog.PACKAGES.get(only)
        if not spec:
            raise SystemExit(f"'{only}' is not in the catalog")
        args.append(f"{only}/{spec['version']}")
    args += profile_args(target)
    # A profile's [conf] does not take part in a package id, so editing one leaves the
    # existing binary looking current and --build=missing reuses it. --rebuild is how to
    # pick a conf change up without hunting down the package in the cache by hand.
    if rebuild:
        names = [only] if only else catalog.packages_for(target)
        args += [f"--build={name}/*" for name in names]
    args += ["--build=missing"]
    # Keep Conan's generator output out of the source tree; we only want the deployer's.
    args += ["-of", os.path.join(ROOT, "build", target), "--envs-generation=false"]
    if os.path.isfile(LOCKFILE):
        args += [f"--lockfile={LOCKFILE}"]
    if deploy_to:
        args += [f"--deployer={DEPLOYER}", f"--deployer-folder={deploy_to}"]
    return args


def cmd_platforms(_args):
    native = native_platform()
    for name in catalog.ALL:
        count = len(catalog.packages_for(name))
        note = "  (this machine)" if name == native else ""
        print(f"{name:<15} {count:>3} packages{note}")


def cmd_packages(args):
    """The whole inventory in one view, which the per-recipe files no longer give."""
    packages = catalog.PACKAGES
    if args.platform:
        packages = catalog.packages_for(args.platform)

    # No target column: a package's targets come from its package_info() and are only
    # known once Conan has resolved it, which listing the inventory does not do.
    print(f"{'package':<22} {'version':<20} rev  platforms")
    for name, spec in sorted(packages.items()):
        print(f"{name:<22} {spec['version']:<20} {spec['rev']:<4} {len(spec['platforms'])}")

    print(f"\n{len(packages)} packages")


def cmd_export(_args):
    names = local_recipes()
    if not names:
        print("no local recipes yet")
        return
    exported = []
    for name in names:
        result = subprocess.run(
            ["conan", "export", os.path.join(RECIPES, name)],
            cwd=ROOT, check=True, capture_output=True, text=True,
        )
        sys.stderr.write(result.stderr)
        for line in (result.stdout + result.stderr).splitlines():
            if line.startswith("Exported: "):
                # 'Exported: name/version#revision (2026-01-01 00:00:00 UTC)'. Only the
                # reference belongs in a lockfile; the parenthesised date is for reading.
                exported.append(line[len("Exported: "):].split(" ")[0].strip())
    relock(exported)


def relock(references):
    """Point the lockfile at the recipes we just exported.

    A lockfile pins a recipe revision, and editing a local recipe produces a new one.
    Left alone, the lockfile keeps resolving the revision from before the edit, so the
    build silently runs the old recipe and the change appears to have done nothing.
    Conan Center entries are untouched: pinning those is the reason the file exists.
    """
    if not os.path.isfile(LOCKFILE) or not references:
        return

    with open(LOCKFILE, encoding="utf8") as handle:
        lock = json.load(handle)

    changed = []
    for section, entries in lock.items():
        if not isinstance(entries, list):
            continue
        for index, entry in enumerate(entries):
            name = entry.split("/")[0]
            for reference in references:
                if reference.split("/")[0] != name:
                    continue
                # The lockfile carries a timestamp after '%'; keep whatever conan
                # reported for the new revision, or drop it if it reported none.
                if entry.split("%")[0] != reference.split("%")[0]:
                    entries[index] = reference
                    changed.append(name)

    if changed:
        with open(LOCKFILE, encoding="utf8") as handle:
            original = handle.read()
        with open(LOCKFILE, "w", encoding="utf8") as handle:
            json.dump(lock, handle, indent=4)
            handle.write("\n")
        if original != open(LOCKFILE, encoding="utf8").read():
            print(f"lockfile updated for {', '.join(sorted(set(changed)))}")


def cmd_build(args):
    cmd_export(args)
    run(install_args(args.platform, only=args.only, rebuild=args.rebuild))


def cmd_package(args):
    cmd_export(args)
    out = args.output or os.path.join(ROOT, "packages", args.platform)
    # The deployer needs the target platform; a graph of one header only package has no
    # settings to infer it from.
    environment = dict(os.environ, O3DE_TARGET_PLATFORM=args.platform)
    run(install_args(args.platform, only=args.only, deploy_to=out,
                     rebuild=args.rebuild), env=environment)
    print(f"\npackages written to {out}")


def cmd_lock(args):
    """Rebuild conan.lock from every platform, so one dependency cannot drift per target."""
    cmd_export(args)
    if os.path.isfile(LOCKFILE):
        os.remove(LOCKFILE)

    staging = os.path.join(ROOT, "build", "next.lock")
    os.makedirs(os.path.dirname(staging), exist_ok=True)
    for target in catalog.ALL:
        command = ["conan", "lock", "create", CONSUMER] + profile_args(target)
        command += [f"--lockfile-out={staging}"]
        if os.path.isfile(LOCKFILE):
            command += [f"--lockfile={LOCKFILE}", "--lockfile-partial"]
        run(command)
        shutil.move(staging, LOCKFILE)
        print(f"  locked {target}")
    print(f"\n{LOCKFILE}")


def cmd_validate(args):
    out = args.output or os.path.join(ROOT, "packages", args.platform)
    run([sys.executable, os.path.join(ROOT, "tools", "validate_package.py"), out])


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("platforms", help="list target platforms").set_defaults(func=cmd_platforms)
    sub.add_parser("export", help="export local recipes to the Conan cache").set_defaults(func=cmd_export)

    packages = sub.add_parser("packages", help="list the package inventory")
    packages.add_argument("platform", nargs="?", help="only packages built for this platform")
    packages.set_defaults(func=cmd_packages)

    build = sub.add_parser("build", help="build a platform into the Conan cache")
    build.add_argument("platform")
    build.add_argument("--only", help="build a single catalog entry")
    build.add_argument("--rebuild", action="store_true",
                       help="build from source even if a binary is cached")
    build.set_defaults(func=cmd_build)

    package = sub.add_parser("package", help="build and write engine packages")
    package.add_argument("platform")
    package.add_argument("--only", help="package a single catalog entry")
    package.add_argument("--rebuild", action="store_true",
                         help="build from source even if a binary is cached")
    package.add_argument("-o", "--output", help="output folder (default packages/<platform>)")
    package.set_defaults(func=cmd_package)

    lock = sub.add_parser("lock", help="rebuild conan.lock across every platform")
    lock.set_defaults(func=cmd_lock)

    validate = sub.add_parser("validate", help="check packages against the engine contract")
    validate.add_argument("platform")
    validate.add_argument("-o", "--output", help="folder to validate (default packages/<platform>)")
    validate.set_defaults(func=cmd_validate)

    args = parser.parse_args()
    try:
        args.func(args)
    except subprocess.CalledProcessError as exc:
        raise SystemExit(exc.returncode)


if __name__ == "__main__":
    main()
