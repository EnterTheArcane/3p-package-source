#
# Copyright (c) Contributors to the Open 3D Engine Project.
# For complete copyright and license terms please see the LICENSE at the root of this distribution.
#
# SPDX-License-Identifier: Apache-2.0 OR MIT
#

"""Finding the checkout these commands act on, and the code that does the work.

A custom command is installed into the Conan home, not into the repository, so unlike a
script it cannot find the repository beside itself. It works the way conan's own commands
do instead: on the directory you are standing in. That also means one installed copy
serves every checkout.
"""

import argparse
import importlib.util
import os

from conan.errors import ConanException

MARKERS = ("recipes", "profiles", "consumer")


def repo_root(start=None):
    """The checkout containing the current directory."""
    current = os.path.abspath(start or os.getcwd())
    while True:
        if all(os.path.isdir(os.path.join(current, marker)) for marker in MARKERS):
            return current
        parent = os.path.dirname(current)
        if parent == current:
            # ConanException rather than SystemExit: conan formats its own errors and
            # treats a bare SystemExit's message as an exit code.
            raise ConanException(
                "not inside a third party checkout: no directory at or above "
                f"{os.getcwd()} holds {', '.join(MARKERS)}"
            )
        current = parent


def implementation(root=None):
    """The module holding what the commands actually run.

    Loaded from the checkout rather than imported, so the code that runs is the code in
    the tree in front of you, not whatever was installed into the Conan home.
    """
    root = root or repo_root()
    path = os.path.join(root, "tools", "cli.py")
    spec = importlib.util.spec_from_file_location("_3p_cli", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def options(**values):
    """The plain namespace the implementation expects."""
    return argparse.Namespace(**values)
