#!/usr/bin/env python3
#
# Copyright (c) Contributors to the Open 3D Engine Project.
# For complete copyright and license terms please see the LICENSE at the root of this distribution.
#
# SPDX-License-Identifier: Apache-2.0 OR MIT
#

"""Emit the target, runner, and native build profile for every O3DE platform."""

import json
import os
import sys

PLATFORMS = {
    "windows-x64": ("windows-2025", "windows-x64"),
    "windows-arm": ("windows-2025", "windows-x64"),
    "linux-x64": ("ubuntu-24.04", "linux-x64"),
    "linux-arm": ("ubuntu-24.04", "linux-x64"),
    "android-arm": ("ubuntu-24.04", "linux-x64"),
    "android-x64": ("ubuntu-24.04", "linux-x64"),
    "emscripten": ("ubuntu-24.04", "linux-x64"),
    "mac-x64": ("macos-26", "mac-arm"),
    "mac-arm": ("macos-26", "mac-arm"),
    "ios-arm": ("macos-26", "mac-arm"),
    "ios-simulator": ("macos-26", "mac-arm"),
}


def main():
    only = (os.environ.get("ONLY_PLATFORM") or "").strip()

    platforms = list(PLATFORMS)
    if only:
        if only not in platforms:
            raise SystemExit(f"unknown platform '{only}'")
        platforms = [only]

    entries = []
    for platform in platforms:
        runner, build_profile = PLATFORMS[platform]
        entries.append({
            "platform": platform,
            "runner": runner,
            "build_profile": build_profile,
        })
    print(f"platforms={json.dumps(entries)}")
    print(f"Selected {len(entries)} platform(s)", file=sys.stderr)


if __name__ == "__main__":
    main()
