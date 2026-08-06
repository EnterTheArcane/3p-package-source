#!/usr/bin/env python3
#
# Copyright (c) Contributors to the Open 3D Engine Project.
# For complete copyright and license terms please see the LICENSE at the root of this distribution.
#
# SPDX-License-Identifier: Apache-2.0 OR MIT
#

"""Refuse to republish a package name with different contents.

The engine pins packages by hash and fetches them by name from a CDN that never
serves two different files under one name. If a rebuilt package differs from what is
already published, its rev in recipes/<name>/package.yml needs bumping. A rebuild that matches
byte for byte is fine and simply has nothing to publish.
"""

import argparse
import json
import os
import sys
import urllib.error
import urllib.request

HASH_EXT = ".tar.xz.SHA256SUMS"


def published_hash(cdn, package):
    """The hash of an already published package, or None if it is not published."""
    url = f"{cdn.rstrip('/')}/{package}{HASH_EXT}"
    try:
        with urllib.request.urlopen(url, timeout=30) as response:
            text = response.read().decode("utf8").strip()
    except urllib.error.HTTPError as error:
        if error.code in (403, 404):
            return None
        raise
    space = text.find(" ")
    return text[:space] if space == 64 else None


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("folder")
    parser.add_argument("--cdn", default=os.environ.get("PROD_CDN"))
    args = parser.parse_args()

    if not args.cdn:
        print("no CDN configured, skipping the published package check")
        return

    with open(os.path.join(args.folder, "packages-manifest.json"), encoding="utf8") as handle:
        manifest = json.load(handle)

    conflicts, unchanged, fresh = [], [], []
    for package in manifest["packages"]:
        name = package["package_name"]
        existing = published_hash(args.cdn, name)
        if existing is None:
            fresh.append(name)
        elif existing == package["sha256"]:
            unchanged.append(name)
        else:
            conflicts.append(name)

    for name in fresh:
        print(f"  new       {name}")
    for name in unchanged:
        print(f"  published {name} (identical)")
    for name in conflicts:
        print(f"  CONFLICT  {name}", file=sys.stderr)

    if conflicts:
        print(
            "\nThese packages are already published with different contents. "
            "Bump their rev in recipes/<name>/package.yml.",
            file=sys.stderr,
        )
        raise SystemExit(1)

    print(f"\n{len(fresh)} new, {len(unchanged)} already published.")


if __name__ == "__main__":
    main()
