#!/usr/bin/env python3
#
# Copyright (c) Contributors to the Open 3D Engine Project.
# For complete copyright and license terms please see the LICENSE at the root of this distribution.
#
# SPDX-License-Identifier: Apache-2.0 OR MIT
#

"""Emit the build matrix, pairing each platform with the runner that builds it.

Everything cross compiles, so the eleven platforms collapse onto three runner images.
Set ONLY_PLATFORM to build a single one.
"""

import importlib.util
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

RUNNERS = {
    "windows-x64": "windows-2025",
    "windows-arm": "windows-2025",
    "linux-x64": "ubuntu-24.04",
    "linux-arm": "ubuntu-24.04",
    "android-arm": "ubuntu-24.04",
    "android-x64": "ubuntu-24.04",
    "emscripten": "ubuntu-24.04",
    "mac-x64": "macos-26",
    "mac-arm": "macos-26",
    "ios-arm": "macos-26",
    "ios-simulator": "macos-26",
}


def load_catalog():
    path = os.path.join(ROOT, "tools", "catalog.py")
    spec = importlib.util.spec_from_file_location("_3p_catalog", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    catalog = load_catalog()
    only = (os.environ.get("ONLY_PLATFORM") or "").strip()

    platforms = list(catalog.ALL)
    if only:
        if only not in platforms:
            raise SystemExit(f"unknown platform '{only}'")
        platforms = [only]

    missing = [p for p in platforms if p not in RUNNERS]
    if missing:
        raise SystemExit(f"no runner mapped for: {', '.join(missing)}")

    # Skip platforms with nothing to build so the matrix does not carry empty jobs.
    entries = [
        {"platform": p, "runner": RUNNERS[p]}
        for p in platforms
        if catalog.packages_for(p)
    ]
    print(f"platforms={json.dumps(entries)}")
    print(f"Selected {len(entries)} platform(s)", file=sys.stderr)


if __name__ == "__main__":
    main()
